from __future__ import annotations

import pytest

from bot_orchestrator.shared.consult_jobs import (
    ConsultJob,
    ConsultJobStatus,
    InMemoryConsultJobRepository,
    estimated_wait_seconds,
)
from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
from bot_orchestrator.slices.run_turn.use_case import _enqueue_consult_job
from bot_orchestrator.workers import consult_worker


class FakeVehicleClient:
    async def check_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
    ) -> dict[str, object]:
        return {
            "placa": placa,
            "vehiculo": {"marca": "Mazda", "linea": "2", "modelo": 2020},
            "soat": {"fechaVencimiento": "2026-10-15", "diasRestantes": 100, "vigente": True},
            "rtm": {"fechaVencimiento": "2026-11-20", "diasRestantes": 136, "tieneRTMVigente": True},
        }

    async def consult_multas(self, *, documento: str, ciudad: str | None = None) -> dict[str, object]:
        return {
            "tieneMultas": True,
            "resumen": {"total": "$500.000", "comparendos": 1, "multas": 1},
        }


class FakeNotificationClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, str]] = []
        self.dispatches: int = 0

    async def send_whatsapp_message(self, *, to: str, body: str) -> dict[str, object]:
        self.sent_messages.append({"to": to, "body": body})
        return {"success": True, "message": {}}

    async def dispatch_outbox(self, *, limit: int = 10) -> dict[str, object]:
        self.dispatches += 1
        return {"dispatched": []}


class FakeQuoteClient:
    async def create(self, **kwargs: object) -> dict[str, object]:
        return {"id": "q-1", "precio": "$150.000"}


class TestConsultJobs:
    def test_enqueue_and_position(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        _, pos = repo.enqueue(job)
        assert pos == 1
        assert repo.count_pending() == 1

        job2 = ConsultJob(
            job_id="job-2",
            user_key="573001112233",
            channel="whatsapp",
            intent="multas",
            documento="123456789",
        )
        _, pos2 = repo.enqueue(job2)
        assert pos2 == 2
        assert repo.count_pending() == 2

        assert repo.get_position("job-1") == 1
        assert repo.get_position("job-2") == 2

    def test_dequeue_atomic(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)

        dequeued = repo.dequeue_next_pending()
        assert dequeued is not None
        assert dequeued.job_id == "job-1"
        assert dequeued.status == ConsultJobStatus.PROCESSING

        # Second dequeue returns None since the only job is now PROCESSING
        assert repo.dequeue_next_pending() is None

        # get_position returns None for non-pending job
        assert repo.get_position("job-1") is None

    def test_mark_done(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)
        dequeued = repo.dequeue_next_pending()
        assert dequeued is not None

        result_data = {"data": {"soat": {}}, "formatted": "SOAT vigente"}
        repo.mark_done("job-1", result_data)
        done_job = repo.get("job-1")
        assert done_job.status == ConsultJobStatus.DONE
        assert done_job.result == result_data
        assert done_job.completed_at is not None

    def test_mark_failed(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)
        dequeued = repo.dequeue_next_pending()
        assert dequeued is not None

        repo.mark_failed("job-1", "Error de prueba")
        failed_job = repo.get("job-1")
        assert failed_job.status == ConsultJobStatus.FAILED
        assert failed_job.error_message == "Error de prueba"

    def test_backpressure_max_queue(self):
        repo = InMemoryConsultJobRepository()
        for i in range(repo.MAX_PENDING_JOBS):
            repo.enqueue(
                ConsultJob(
                    job_id=f"job-{i}",
                    user_key="573001112233",
                    channel="whatsapp",
                    intent="soat",
                    placa="ABC123",
                    documento="123456789",
                )
            )

        with pytest.raises(RuntimeError, match="cola de consultas esta llena"):
            repo.enqueue(
                ConsultJob(
                    job_id="job-overflow",
                    user_key="573001112233",
                    channel="whatsapp",
                    intent="soat",
                    placa="ABC123",
                    documento="123456789",
                )
            )

    def test_find_active_for_user_no_match(self):
        repo = InMemoryConsultJobRepository()
        result = repo.find_active_for_user(
            user_key="573001112233", intent="soat", max_age_seconds=120
        )
        assert result is None

    def test_find_active_for_user_returns_pending_job(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)
        result = repo.find_active_for_user(
            user_key="573001112233", intent="soat", max_age_seconds=120
        )
        assert result is not None
        job_result, pos = result
        assert job_result.job_id == "job-1"
        assert pos == 1
        assert job_result.status == ConsultJobStatus.PENDING

    def test_find_active_for_user_returns_processing_job(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)
        repo.dequeue_next_pending()  # Moves to PROCESSING
        result = repo.find_active_for_user(
            user_key="573001112233", intent="soat", max_age_seconds=120
        )
        assert result is not None
        job_result, pos = result
        assert job_result.status == ConsultJobStatus.PROCESSING

    def test_find_active_for_user_wrong_intent(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)
        result = repo.find_active_for_user(
            user_key="573001112233", intent="multas", max_age_seconds=120
        )
        assert result is None

    def test_reap_stuck_jobs_nothing_to_reap(self):
        repo = InMemoryConsultJobRepository()
        reaped = repo.reap_stuck_jobs(max_processing_seconds=300)
        assert reaped == []

    def test_reap_stuck_jobs_marks_old_processing_as_failed(self):
        import datetime as dt

        repo = InMemoryConsultJobRepository()
        # Create a job with an old created_at to simulate stuck processing
        old_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=400)).isoformat()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
            created_at=old_time,
        )
        repo.enqueue(job)
        repo.dequeue_next_pending()  # Moves to PROCESSING

        # Reap with 300s timeout — this job is 400s old, should be reaped
        reaped = repo.reap_stuck_jobs(max_processing_seconds=300)
        assert len(reaped) == 1
        assert reaped[0].job_id == "job-1"

        # Job should now be failed
        failed_job = repo.get("job-1")
        assert failed_job.status == ConsultJobStatus.FAILED
        assert "Stuck in processing" in failed_job.error_message

    def test_clear_all(self):
        repo = InMemoryConsultJobRepository()
        repo.enqueue(
            ConsultJob(
                job_id="job-1",
                user_key="573001112233",
                channel="whatsapp",
                intent="soat",
                placa="ABC123",
                documento="123456789",
            )
        )
        assert repo.count_pending() == 1
        repo.clear_all()
        assert repo.count_pending() == 0
        assert repo.dequeue_next_pending() is None


class TestConsultWorker:
    @pytest.mark.asyncio
    async def test_process_one_job_soat(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-1",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa="ABC123",
            documento="123456789",
        )
        repo.enqueue(job)
        dequeued = repo.dequeue_next_pending()
        assert dequeued is not None

        fake_vc = FakeVehicleClient()
        fake_nc = FakeNotificationClient()
        fake_qc = FakeQuoteClient()
        await consult_worker.process_one_job(
            dequeued,
            repository=repo,
            vehicle_client=fake_vc,
            notification_client=fake_nc,
            quote_client=fake_qc,
        )

        assert len(fake_nc.sent_messages) == 1
        assert "SOAT vigente hasta el *15/10/2026*" in fake_nc.sent_messages[0]["body"]
        assert fake_nc.dispatches == 1

        done_job = repo.get("job-1")
        assert done_job.status == ConsultJobStatus.DONE
        assert done_job.result is not None

    @pytest.mark.asyncio
    async def test_process_one_job_multas(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-2",
            user_key="573001112233",
            channel="whatsapp",
            intent="multas",
            documento="123456789",
        )
        repo.enqueue(job)
        dequeued = repo.dequeue_next_pending()
        assert dequeued is not None

        fake_vc = FakeVehicleClient()
        fake_nc = FakeNotificationClient()
        fake_qc = FakeQuoteClient()
        await consult_worker.process_one_job(
            dequeued,
            repository=repo,
            vehicle_client=fake_vc,
            notification_client=fake_nc,
            quote_client=fake_qc,
        )

        assert len(fake_nc.sent_messages) == 1
        assert "multas/comparendos" in fake_nc.sent_messages[0]["body"]
        assert fake_nc.dispatches == 1

        done_job = repo.get("job-2")
        assert done_job.status == ConsultJobStatus.DONE

    @pytest.mark.asyncio
    async def test_process_one_job_with_error_sends_failure_notification(self):
        repo = InMemoryConsultJobRepository()
        job = ConsultJob(
            job_id="job-3",
            user_key="573001112233",
            channel="whatsapp",
            intent="soat",
            placa=None,  # Missing placa → error
            documento="123456789",
        )
        repo.enqueue(job)
        dequeued = repo.dequeue_next_pending()
        assert dequeued is not None

        fake_vc = FakeVehicleClient()
        fake_nc = FakeNotificationClient()
        fake_qc = FakeQuoteClient()
        await consult_worker.process_one_job(
            dequeued,
            repository=repo,
            vehicle_client=fake_vc,
            notification_client=fake_nc,
            quote_client=fake_qc,
        )

        # Job marked failed
        failed_job = repo.get("job-3")
        assert failed_job.status == ConsultJobStatus.FAILED

        # Error notification sent
        assert len(fake_nc.sent_messages) == 1
        assert "problema consultando" in fake_nc.sent_messages[0]["body"]
        assert fake_nc.dispatches == 1

    @pytest.mark.asyncio
    async def test_run_once_processes_multiple_jobs_in_parallel(self):
        repo = InMemoryConsultJobRepository()
        # Enqueue 3 jobs
        for i in range(3):
            repo.enqueue(
                ConsultJob(
                    job_id=f"job-{i}",
                    user_key=f"57300111223{i}",
                    channel="whatsapp",
                    intent="multas",
                    documento="123456789",
                )
            )

        fake_vc = FakeVehicleClient()
        fake_nc = FakeNotificationClient()
        fake_qc = FakeQuoteClient()
        processed = await consult_worker.run_once(
            repository=repo,
            vehicle_client=fake_vc,
            notification_client=fake_nc,
            quote_client=fake_qc,
            max_concurrent=3,
        )
        assert processed == 3
        # All 3 jobs should be done
        for i in range(3):
            job = repo.get(f"job-{i}")
            assert job.status == ConsultJobStatus.DONE
        # 3 notifications sent, 3 dispatches
        assert len(fake_nc.sent_messages) == 3
        assert fake_nc.dispatches == 3

    @pytest.mark.asyncio
    async def test_run_once_with_max_concurrent_1_is_serial(self):
        repo = InMemoryConsultJobRepository()
        for i in range(2):
            repo.enqueue(
                ConsultJob(
                    job_id=f"job-{i}",
                    user_key=f"57300111223{i}",
                    channel="whatsapp",
                    intent="multas",
                    documento="123456789",
                )
            )

        fake_vc = FakeVehicleClient()
        fake_nc = FakeNotificationClient()
        fake_qc = FakeQuoteClient()
        processed = await consult_worker.run_once(
            repository=repo,
            vehicle_client=fake_vc,
            notification_client=fake_nc,
            quote_client=fake_qc,
            max_concurrent=1,
        )
        assert processed == 1
        # Only 1 job processed
        pending = repo.count_pending()
        assert pending == 1

    @pytest.mark.asyncio
    async def test_enqueue_consult_job_integration(self):
        repo = InMemoryConsultJobRepository()
        response = await _enqueue_consult_job(
            payload=AgentTurnRequest(
                user_key="573001112233",
                text="consulta soat ABC123 123456789",
                channel="whatsapp",
            ),
            intent="soat",
            placa="ABC123",
            documento="123456789",
            repository=repo,
        )
        assert response.mode == "vehicle_soat_queued"
        assert "ya empiezo a consultar" in response.text
        assert repo.count_pending() == 1

    @pytest.mark.asyncio
    async def test_enqueue_consult_job_position_message(self):
        repo = InMemoryConsultJobRepository()
        # Pre-fill with one job
        for i in range(3):
            repo.enqueue(
                ConsultJob(
                    job_id=f"pre-{i}",
                    user_key="573001112233",
                    channel="whatsapp",
                    intent="soat",
                    placa="ABC123",
                    documento="123456789",
                )
            )

        response = await _enqueue_consult_job(
            payload=AgentTurnRequest(
                user_key="573001112233",
                text="consulta tecno XYZ999 123456789",
                channel="whatsapp",
            ),
            intent="tecnomecanica",
            placa="XYZ999",
            documento="123456789",
            repository=repo,
        )
        assert "posicion *4*" in response.text

    @pytest.mark.asyncio
    async def test_enqueue_consult_job_dedup_returns_existing(self, monkeypatch):
        """When a pending job already exists for the same user+intent, reuse it."""
        repo = InMemoryConsultJobRepository()
        # Pre-queue a job for the same user+intent
        repo.enqueue(
            ConsultJob(
                job_id="existing-1",
                user_key="573001112233",
                channel="whatsapp",
                intent="soat",
                placa="ABC123",
                documento="123456789",
            )
        )

        monkeypatch.setenv("BOT_CONSULT_DEDUP_WINDOW_SECONDS", "300")

        response = await _enqueue_consult_job(
            payload=AgentTurnRequest(
                user_key="573001112233",
                text="consulta soat ABC123 123456789",
                channel="whatsapp",
            ),
            intent="soat",
            placa="ABC123",
            documento="123456789",
            repository=repo,
        )
        assert response.mode == "vehicle_soat_already_queued"
        assert "Ya tienes una consulta" in response.text
        assert "posicion *1*" in response.text
        # Only 1 job should exist — no duplicate was created
        assert repo.count_pending() == 1

    @pytest.mark.asyncio
    async def test_enqueue_consult_job_no_dedup_when_disabled(self, monkeypatch):
        """When dedup window is 0, always create a new job."""
        repo = InMemoryConsultJobRepository()
        repo.enqueue(
            ConsultJob(
                job_id="existing-1",
                user_key="573001112233",
                channel="whatsapp",
                intent="soat",
                placa="ABC123",
                documento="123456789",
            )
        )

        monkeypatch.setenv("BOT_CONSULT_DEDUP_WINDOW_SECONDS", "0")

        response = await _enqueue_consult_job(
            payload=AgentTurnRequest(
                user_key="573001112233",
                text="consulta soat ABC123 123456789",
                channel="whatsapp",
            ),
            intent="soat",
            placa="ABC123",
            documento="123456789",
            repository=repo,
        )
        assert response.mode == "vehicle_soat_queued"
        assert repo.count_pending() == 2


def test_estimated_wait_seconds():
    # parallelism=1: position 1 = 0s (no one ahead), position 3 = 50s (2 ahead)
    assert "~0 segundos" == estimated_wait_seconds(1)
    assert "~50 segundos" == estimated_wait_seconds(3)
    assert "~1 min 40 s" == estimated_wait_seconds(5)
    assert "~7 min 55 s" == estimated_wait_seconds(20)


def test_estimated_wait_seconds_with_parallelism():
    # With parallelism=3, positions 1-3 go together, 4-6 go together, etc.
    assert "~0 segundos" == estimated_wait_seconds(1, parallelism=3)
    assert "~0 segundos" == estimated_wait_seconds(2, parallelism=3)
    assert "~0 segundos" == estimated_wait_seconds(3, parallelism=3)
    assert "~25 segundos" == estimated_wait_seconds(4, parallelism=3)
    assert "~25 segundos" == estimated_wait_seconds(5, parallelism=3)
    assert "~25 segundos" == estimated_wait_seconds(6, parallelism=3)
    assert "~50 segundos" == estimated_wait_seconds(7, parallelism=3)
