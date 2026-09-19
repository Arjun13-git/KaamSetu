import app.core.ids as ids
from app.core.ids import IdPrefix, new_id
from seed.determinism import readable_ids


def test_ids_inside_the_block_are_readable_and_count_from_zero() -> None:
    with readable_ids("gas_refill"):
        first, second = new_id(IdPrefix.JOB), new_id(IdPrefix.AUDIT)

    assert first == "job_demo_gas_refill_0"
    assert second == "aud_demo_gas_refill_1"


def test_the_same_block_always_yields_the_same_ids() -> None:
    def run() -> list[str]:
        with readable_ids("x"):
            return [new_id(IdPrefix.JOB), new_id(IdPrefix.SERVICE_EVENT)]

    assert run() == run()


def test_each_block_starts_its_own_count() -> None:
    with readable_ids("a"):
        new_id(IdPrefix.JOB)
        new_id(IdPrefix.JOB)
    with readable_ids("b"):
        assert new_id(IdPrefix.JOB) == "job_demo_b_0"


def test_production_id_generation_is_restored_afterwards_even_after_an_error() -> None:
    original = ids.uuid4

    try:
        with readable_ids("boom"):
            raise RuntimeError("fail inside the block")
    except RuntimeError:
        pass

    assert ids.uuid4 is original
    assert new_id(IdPrefix.JOB) != new_id(IdPrefix.JOB)  # random again
    assert "demo_" not in new_id(IdPrefix.JOB)
