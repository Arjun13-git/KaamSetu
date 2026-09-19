"""The deterministic demo dataset: what it contains, that it is repeatable and safe to rerun, and
that each of the five demo scenarios really works through the API on top of it."""

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

import pytest
from moto import mock_aws

from app.ai.extractor import IntakeExtractor
from app.domain.enums import JobStatus, ServiceRequestStatus
from app.domain.repositories import Repositories
from app.providers.persistence.dynamodb.client import build_resource
from app.providers.persistence.dynamodb.table import create_table
from app.providers.persistence.memory import build_in_memory_repositories
from seed import __main__ as seed_cli
from seed.dataset import DEFAULT_AS_OF, build_demo_plan
from seed.plan import apply_plan
from seed.sample_data import load_demo_data
from seed.verify import check_demo_data, counts, digest, snapshot
from tests.ai_support import ScriptedLLM, valid_extraction
from tests.api_support import TENANT, Api, build_api, dev_settings

ACTOR = "usr_dev"
# Update deliberately when the dataset changes: this proves the data is identical on every machine.
GOLDEN_DIGEST = "67cd4bfd5a8185824ac4e92f61bc1b3166d11f3d281dcc638b01d618134f67ff"


def load(repos: Repositories, as_of: dt.datetime = DEFAULT_AS_OF) -> Any:
    return load_demo_data(repos, business_id=TENANT, actor_id=ACTOR, as_of=as_of)


def reference_digest() -> str:
    """The dataset as loaded into a fresh in-memory store."""
    fresh = build_in_memory_repositories()
    load(fresh)
    return digest(snapshot(fresh, TENANT))


@pytest.fixture
def seeded(repos: Repositories) -> Any:
    return load(repos)


def _api_with(repos: Repositories, *script: dict[str, Any]) -> tuple[Api, ScriptedLLM]:
    llm = ScriptedLLM(*script)
    extractor = IntakeExtractor(llm, model_id="test-model", max_retries=0)
    return build_api(repos, settings=dev_settings(), extractor=extractor), llm


class TestTheDataset:
    def test_every_check_passes(self, repos: Repositories, seeded: Any) -> None:
        failures = [
            f"{name}: {detail}"
            for name, ok, detail in check_demo_data(repos, TENANT, seeded.manifest)
            if not ok
        ]

        assert failures == []

    def test_what_was_written(self, repos: Repositories, seeded: Any) -> None:
        assert counts(snapshot(repos, TENANT)) == {
            "businesses": 1,
            "technicians": 4,
            "customers": 7,
            "assets": 12,
            "service_requests": 14,
            "jobs": 13,
            "service_events": 6,
            "audits": 78,
        }
        assert seeded.total_created == 118 and seeded.total_existing == 0

    def test_ids_are_readable_and_stable(self, seeded: Any) -> None:
        manifest = seeded.manifest

        assert manifest["customers"]["ravi_kumar"] == "cus_demo_ravi_kumar"
        assert manifest["assets"]["ravi_lg_ac"] == "ast_demo_ravi_lg_ac"
        assert manifest["technicians"]["imran"] == "tec_demo_imran"
        assert manifest["service_requests"]["new_customer_deepak"] == "srq_demo_new_customer_deepak"
        assert manifest["jobs"]["gas_refill_ravi_lg_ac"] == "job_demo_gas_refill_ravi_lg_ac_0"

    def test_every_job_came_from_a_service_request(self, repos: Repositories, seeded: Any) -> None:
        for job in repos.jobs.list(TENANT):
            request = repos.service_requests.get(TENANT, job.service_request_id or "")
            assert request.status is ServiceRequestStatus.JOB_CREATED
            assert request.job_id == job.job_id

    def test_no_timestamp_is_after_the_as_of_instant(
        self, repos: Repositories, seeded: Any
    ) -> None:
        latest = max(
            dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            for rows in snapshot(repos, TENANT).values()
            for row in rows
            for key, value in row.items()
            if key in {"created_at", "updated_at", "timestamp", "completed_at"} and value
        )

        assert latest <= DEFAULT_AS_OF

    def test_intake_fixtures_are_labelled_as_fixtures_not_model_output(
        self, repos: Repositories, seeded: Any
    ) -> None:
        for request in repos.service_requests.list(TENANT):
            if request.extraction:
                assert request.extraction["model_id"] == "seed-fixture"
                assert request.extraction["prompt_version"] == "seed-fixture"

    def test_all_names_and_numbers_are_the_fictional_ones(
        self, repos: Repositories, seeded: Any
    ) -> None:
        people = repos.customers.list(TENANT) + repos.technicians.list(TENANT)  # type: ignore[operator]

        assert all(re.fullmatch(r"\+919000\d{6}", p.phone or "") for p in people)
        assert not any(getattr(c, "email", None) for c in repos.customers.list(TENANT))


class TestDocumentation:
    def test_the_readme_lists_every_job_technician_and_the_review_request(self) -> None:
        readme = (Path(__file__).resolve().parents[2] / "seed" / "README.md").read_text()
        manifest = build_demo_plan(TENANT, ACTOR).manifest

        missing = [
            *(f"job {key}" for key in manifest["jobs"] if f"`{key}`" not in readme),
            *(
                f"technician {key}"
                for key in manifest["technicians"]
                if f"tec_demo_{key}" not in readme
            ),
            *(f"request {key}" for key in ("new_customer_deepak",) if f"`{key}`" not in readme),
        ]

        assert missing == []


class TestDeterminism:
    def test_two_independent_loads_are_identical(self, repos: Repositories, seeded: Any) -> None:
        assert digest(snapshot(repos, TENANT)) == reference_digest()

    def test_every_adapter_stores_exactly_the_same_dataset(
        self, repos: Repositories, seeded: Any
    ) -> None:
        """Memory, DynamoDB (moto) and, when enabled, DynamoDB Local read back identically."""
        assert snapshot(repos, TENANT) == snapshot(_reference_store(), TENANT)

    def test_the_dataset_matches_its_pinned_fingerprint(self) -> None:
        assert reference_digest() == GOLDEN_DIGEST

    def test_the_as_of_instant_moves_times_and_nothing_else(self) -> None:
        later = DEFAULT_AS_OF + dt.timedelta(days=3)
        a, b = build_demo_plan(TENANT, ACTOR, DEFAULT_AS_OF), build_demo_plan(TENANT, ACTOR, later)

        assert a.manifest["jobs"] == b.manifest["jobs"]
        assert a.manifest["customers"] == b.manifest["customers"]
        fresh_a, fresh_b = build_in_memory_repositories(), build_in_memory_repositories()
        apply_plan(a.ops, fresh_a)
        apply_plan(b.ops, fresh_b)
        rows_a, rows_b = snapshot(fresh_a, TENANT), snapshot(fresh_b, TENANT)
        assert digest(rows_a) != digest(rows_b)
        assert [j["job_id"] for j in rows_a["jobs"]] == [j["job_id"] for j in rows_b["jobs"]]
        assert [j["status"] for j in rows_a["jobs"]] == [j["status"] for j in rows_b["jobs"]]

    def test_a_naive_as_of_is_refused(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            build_demo_plan(TENANT, ACTOR, dt.datetime(2026, 9, 19, 10, 0))


_REFERENCE: list[Repositories] = []


def _reference_store() -> Repositories:
    if not _REFERENCE:
        store = build_in_memory_repositories()
        load(store)
        _REFERENCE.append(store)
    return _REFERENCE[0]


class _Budget:
    def __init__(self, writes: int) -> None:
        self.left = writes


class _Flaky:
    """Passes everything through, but 'crashes' once its shared write budget is spent."""

    _WRITES = {"create", "update", "complete", "append", "create_for_request"}

    def __init__(self, inner: Any, budget: _Budget) -> None:
        self._inner, self._budget = inner, budget

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name not in self._WRITES:
            return attribute

        def guarded(*args: Any, **kwargs: Any) -> Any:
            if self._budget.left <= 0:
                raise RuntimeError("simulated crash")
            self._budget.left -= 1
            return attribute(*args, **kwargs)

        return guarded


def _crashing(repos: Repositories, writes: int) -> Repositories:
    budget = _Budget(writes)
    return Repositories(
        **{name: _Flaky(getattr(repos, name), budget) for name in repos.__slots__}  # type: ignore[arg-type]
    )


class TestIdempotency:
    def test_running_it_again_writes_nothing_and_changes_nothing(
        self, repos: Repositories, seeded: Any
    ) -> None:
        before = snapshot(repos, TENANT)

        again = load(repos)

        assert again.total_created == 0 and again.total_existing == 118
        assert snapshot(repos, TENANT) == before

    def test_it_never_undoes_what_people_did_after_seeding(
        self, repos: Repositories, seeded: Any
    ) -> None:
        api = build_api(repos)
        job_id = seeded.manifest["jobs"]["ro_flow_low_meena"]
        api.call(
            "POST",
            f"/jobs/{job_id}/assign",
            {"technician_id": seeded.manifest["technicians"]["suresh"]},
            expect=200,
        )
        edited = snapshot(repos, TENANT)

        again = load(repos)

        assert again.total_created == 0
        assert snapshot(repos, TENANT) == edited
        assert repos.jobs.get(TENANT, job_id).status is JobStatus.ASSIGNED

    @pytest.mark.parametrize("crash_after", [1, 9, 40, 75, 110])
    def test_an_interrupted_load_is_completed_not_duplicated(
        self, repos: Repositories, crash_after: int
    ) -> None:
        with pytest.raises(RuntimeError, match="simulated crash"):
            load_demo_data(
                _crashing(repos, crash_after),
                business_id=TENANT,
                actor_id=ACTOR,
                as_of=DEFAULT_AS_OF,
            )

        resumed = load(repos)

        assert resumed.total_created > 0
        assert digest(snapshot(repos, TENANT)) == GOLDEN_DIGEST
        assert load(repos).total_created == 0

    def test_two_interruptions_in_a_row_still_converge(self, repos: Repositories) -> None:
        for budget in (30, 45):
            with pytest.raises(RuntimeError):
                load_demo_data(
                    _crashing(repos, budget),
                    business_id=TENANT,
                    actor_id=ACTOR,
                    as_of=DEFAULT_AS_OF,
                )

        load(repos)

        assert digest(snapshot(repos, TENANT)) == GOLDEN_DIGEST


class TestScenariosThroughTheApi:
    """Each scenario, driven through the real endpoints on the seeded data. The model is scripted
    so the checks are exact; what they prove is what the *application* does with the data."""

    def test_1_a_repeat_ac_complaint_surfaces_the_history(
        self, repos: Repositories, seeded: Any
    ) -> None:
        api, _ = _api_with(repos, valid_extraction())  # LG AC, "not cooling"
        events = seeded.manifest["events"]

        history = api.call(
            "GET", f"/assets/{seeded.manifest['assets']['ravi_lg_ac']}/history", expect=200
        )
        out = api.call(
            "POST",
            "/intake",
            {"text": "Bhaiya LG AC phir se thanda nahi kar raha", "phone": "90000 20001"},
            expect=201,
        )

        expected = [events["gas_refill_ravi_lg_ac"], events["annual_service_ravi_lg_ac"]]
        assert [e["event_id"] for e in history["service_events"]] == expected
        assert out["outcome"] == "job_created"
        assert out["job"]["customer_id"] == seeded.manifest["customers"]["ravi_kumar"]
        assert out["job"]["asset_id"] == seeded.manifest["assets"]["ravi_lg_ac"]
        assert [e["event_id"] for e in out["prior_service"]] == expected  # and not the fridge
        assert out["prior_service"][0]["work_performed"] == (
            "Gas pressure checked and refrigerant refilled"
        )

    def test_2_a_customer_with_several_assets_is_never_guessed(
        self, repos: Repositories, seeded: Any
    ) -> None:
        no_brand = valid_extraction(asset={"type": "air_conditioner", "brand": None, "model": None})
        api, _ = _api_with(repos, no_brand, valid_extraction())
        meena = seeded.manifest["customers"]["meena_iyer"]

        listed = api.call("GET", f"/customers/{meena}/assets", expect=200)
        vague = api.call(
            "POST",
            "/intake",
            {"text": "AC thanda nahi kar raha", "phone": "90000 20003"},
            expect=201,
        )
        branded = api.call(
            "POST", "/intake", {"text": "LG AC not cooling", "phone": "90000 20003"}, expect=201
        )
        ravis = api.call("GET", "/customers?q=ravi", expect=200)

        assert len(listed) == 4
        assert vague["outcome"] == "needs_review" and vague["job"] is None
        assert vague["service_request"]["asset_resolution"]["state"] == "ambiguous"
        assert branded["job"]["asset_id"] == seeded.manifest["assets"]["meena_lg_ac"]
        assert [c["name"] for c in ravis] == ["Ravi Kumar", "Ravi Verma"]

    def test_3_a_new_customer_waits_for_review(self, repos: Repositories, seeded: Any) -> None:
        godrej = valid_extraction(
            customer_reference="Deepak",
            asset={"type": "refrigerator", "brand": "Godrej", "model": None},
        )
        api, _ = _api_with(repos, godrej)
        customers_before = len(repos.customers.list(TENANT))

        waiting = api.call("GET", "/service-requests?status=NEEDS_REVIEW", expect=200)
        out = api.call(
            "POST",
            "/intake",
            {"text": "Mere Godrej fridge ka compressor start nahi ho raha", "phone": "90000 29999"},
            expect=201,
        )

        assert [r["service_request_id"] for r in waiting] == [
            seeded.manifest["service_requests"]["new_customer_deepak"]
        ]
        assert waiting[0]["customer_resolution"]["state"] == "new" and waiting[0]["job_id"] is None
        assert out["outcome"] == "needs_review" and out["job"] is None
        assert out["service_request"]["customer_resolution"]["state"] == "new"
        assert len(repos.customers.list(TENANT)) == customers_before  # nobody was created for them

    def test_4_a_safety_critical_request_is_flagged_and_never_diagnosed(
        self, repos: Repositories, seeded: Any
    ) -> None:
        fridge = valid_extraction(asset={"type": "refrigerator", "brand": "Samsung", "model": None})
        api, _ = _api_with(repos, fridge)
        board = api.call("GET", "/jobs?limit=200", expect=200)

        out = api.call(
            "POST",
            "/intake",
            {
                "text": "Fridge se chingari nikal rahi hai aur jalne ki smell aa rahi hai",
                "phone": "90000 20004",
            },
            expect=201,
        )

        urgent = [j for j in board if j["urgency"] == "safety_critical"]
        assert [j["job_id"] for j in urgent] == [
            seeded.manifest["jobs"]["fridge_burning_smell_farhan"]
        ]
        assert urgent[0]["status"] == "NEW" and urgent[0]["technician_id"] is None
        assert out["safety_concern"] is True and out["job"]["urgency"] == "safety_critical"
        assert out["job"]["description"] == "AC not cooling"  # what the (scripted) model reported

    def test_5_the_board_shows_every_status_and_the_lifecycle_can_be_driven(
        self, repos: Repositories, seeded: Any
    ) -> None:
        api = build_api(repos)
        manifest = seeded.manifest
        board = api.call("GET", "/jobs?limit=200", expect=200)
        by_status = {
            s: [j for j in board if j["status"] == s] for s in {j["status"] for j in board}
        }

        assert {s: len(v) for s, v in by_status.items()} == manifest["job_status_counts"]
        kavitha = api.call(
            "GET", f"/jobs?technician_id={manifest['technicians']['kavitha']}", expect=200
        )
        assert sorted(j["status"] for j in kavitha) == [
            "ASSIGNED",
            "CANCELLED",
            "COMPLETED",
            "IN_PROGRESS",
        ]

        # A person drives the open job through the real endpoints, to completion.
        job_id = manifest["jobs"]["ro_flow_low_meena"]
        api.call(
            "POST",
            f"/jobs/{job_id}/assign",
            {"technician_id": manifest["technicians"]["anil"]},
            expect=422,
        )
        api.call(
            "POST",
            f"/jobs/{job_id}/assign",
            {"technician_id": manifest["technicians"]["suresh"]},
            expect=200,
        )
        api.call("POST", f"/jobs/{job_id}/transition", {"to_status": "IN_PROGRESS"}, expect=200)
        done = api.call(
            "POST", f"/jobs/{job_id}/complete", {"work_performed": "Membrane cleaned"}, expect=200
        )
        history = api.call(
            "GET", f"/assets/{manifest['assets']['meena_kent_ro']}/history", expect=200
        )

        assert [e["event_id"] for e in history["service_events"]][0] == done["service_event"][
            "event_id"
        ]
        assert len(history["service_events"]) == 2  # the earlier filter change is still there


class TestCli:
    @pytest.fixture
    def cli_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
        monkeypatch.chdir(tmp_path)  # no stray .env
        for name, value in {
            "APP_ENV": "development",
            "DATA_PROVIDER": "dynamodb",
            "DYNAMODB_TABLE": "seed-cli-test",
            "AWS_REGION": "us-east-1",
        }.items():
            monkeypatch.setenv(name, value)
        with mock_aws():
            create_table(
                build_resource(region="us-east-1", profile=None, endpoint_url=None), "seed-cli-test"
            )
            yield

    def test_load_then_verify_then_reload(
        self, cli_env: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert seed_cli.main([]) == 0
        loaded = capsys.readouterr().out
        assert "Wrote 118 records; 0 were already present." in loaded
        assert f"Digest:  {GOLDEN_DIGEST}" in loaded and "FAIL" not in loaded

        assert seed_cli.main(["--verify"]) == 0
        assert "Wrote" not in capsys.readouterr().out  # read-only

        assert seed_cli.main([]) == 0
        assert "Wrote 0 records; 118 were already present." in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("prefix", "section", "key"),
        [
            ("CUSTOMER", "customers", "nisha_bhat"),
            ("CUSTOMER", "customers", "meena_iyer"),
            ("ASSET", "assets", "ravi_lg_ac"),
            ("JOB", "jobs", "gas_refill_ravi_lg_ac"),
            ("EVENT", "events", "gas_refill_ravi_lg_ac"),
            ("SERVICEREQUEST", "service_requests", "fridge_burning_smell_farhan"),
            ("SERVICEREQUEST", "service_requests", "new_customer_deepak"),
            ("TECHNICIAN", "technicians", "anil"),
        ],
    )
    def test_verify_reports_damage_instead_of_crashing(
        self, cli_env: Any, capsys: pytest.CaptureFixture[str], prefix: str, section: str, key: str
    ) -> None:
        seed_cli.main([])
        capsys.readouterr()
        record_id = build_demo_plan(TENANT, ACTOR).manifest[section][key]
        table = build_resource(region="us-east-1", profile=None, endpoint_url=None).Table(
            "seed-cli-test"
        )
        deleted = table.delete_item(
            Key={"PK": f"BUSINESS#{TENANT}", "SK": f"{prefix}#{record_id}"}, ReturnValues="ALL_OLD"
        )
        assert "Attributes" in deleted  # the record really existed

        assert seed_cli.main(["--verify"]) == 1

        output = capsys.readouterr().out
        assert "FAIL" in output and "Traceback" not in output

    def test_the_manifest_needs_no_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        for name in ("APP_ENV", "DATA_PROVIDER"):
            monkeypatch.delenv(name, raising=False)

        assert seed_cli.main(["--manifest"]) == 0

        manifest = json.loads(capsys.readouterr().out)
        assert len(manifest["jobs"]) == 13 and set(manifest["scenarios"]) == {
            "repeat_ac_complaint",
            "multiple_assets",
            "new_customer_review",
            "safety_critical",
            "job_lifecycle",
        }

    def test_the_memory_provider_is_refused_for_loading(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("DATA_PROVIDER", "memory")

        assert seed_cli.main([]) == 2
        assert "DATA_PROVIDER=dynamodb" in capsys.readouterr().out

    def test_a_naive_as_of_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exit_info:
            seed_cli.main(["--manifest", "--as-of", "2026-09-19T10:00:00"])

        assert exit_info.value.code == 2
