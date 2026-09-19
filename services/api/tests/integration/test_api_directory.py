"""Technicians, assets and customer search: the records jobs are built from."""

from app.domain.enums import AuditAction, AuditEntityType
from tests.api_support import TENANT, Api
from tests.factories import OTHER_BUSINESS_ID, make_asset, make_customer, make_technician


class TestTechnicians:
    def test_create_get_and_audit(self, api: Api) -> None:
        created = api.technician(name="Imran Sheikh", phone="90000 10001", skills=["ac", "fridge"])

        assert created["technician_id"].startswith("tec_")
        assert created["phone"] == "+919000010001" and created["active"] is True
        assert "business_id" not in created
        assert api.call("GET", f"/technicians/{created['technician_id']}", expect=200) == created
        (audit,) = api.repos.audits.list_for_entity(
            TENANT, AuditEntityType.TECHNICIAN, created["technician_id"]
        )
        assert audit.action is AuditAction.TECHNICIAN_CREATED

    def test_list_can_be_limited_to_active_technicians(self, api: Api) -> None:
        api.technician(name="Active One")
        api.repos.technicians.create(
            make_technician(business_id=TENANT, name="Retired", active=False)
        )

        everyone = api.call("GET", "/technicians", expect=200)
        active = api.call("GET", "/technicians?active_only=true", expect=200)

        assert [t["name"] for t in everyone] == ["Active One", "Retired"]
        assert [t["name"] for t in active] == ["Active One"]

    def test_another_business_is_invisible_and_cannot_be_written_via_the_body(
        self, api: Api
    ) -> None:
        foreign = make_technician(business_id=OTHER_BUSINESS_ID)
        api.repos.technicians.create(foreign)

        api.call("GET", f"/technicians/{foreign.technician_id}", expect=404)
        assert api.call("GET", "/technicians", expect=200) == []
        api.call(
            "POST",
            "/technicians",
            {"name": "X", "business_id": OTHER_BUSINESS_ID},
            expect=422,
        )

    def test_invalid_input_is_rejected(self, api: Api) -> None:
        api.call("POST", "/technicians", {"name": " "}, expect=422)
        api.call("POST", "/technicians", {"name": "A", "phone": "abc"}, expect=422)


class TestAssets:
    def test_create_get_list_and_audit(self, api: Api) -> None:
        customer = api.customer()
        asset = api.asset(customer["customer_id"], brand="LG", location="Bedroom")

        assert asset["asset_id"].startswith("ast_")
        assert asset["customer_id"] == customer["customer_id"]
        assert asset["model"] is None and asset["serial_number"] is None  # unknown stays unknown
        assert api.call("GET", f"/assets/{asset['asset_id']}", expect=200) == asset
        listed = api.call("GET", f"/customers/{customer['customer_id']}/assets", expect=200)
        assert [a["asset_id"] for a in listed] == [asset["asset_id"]]
        (audit,) = api.repos.audits.list_for_entity(
            TENANT, AuditEntityType.ASSET, asset["asset_id"]
        )
        assert audit.action is AuditAction.ASSET_CREATED

    def test_an_asset_cannot_be_attached_to_another_businesss_customer(self, api: Api) -> None:
        foreign = make_customer(business_id=OTHER_BUSINESS_ID)
        api.repos.customers.create(foreign)

        api.call(
            "POST",
            f"/customers/{foreign.customer_id}/assets",
            {"asset_type": "air_conditioner"},
            expect=404,
        )
        api.call("GET", f"/customers/{foreign.customer_id}/assets", expect=404)

    def test_assets_of_another_business_are_invisible(self, api: Api) -> None:
        foreign_customer = make_customer(business_id=OTHER_BUSINESS_ID)
        foreign_asset = make_asset(foreign_customer)
        api.repos.customers.create(foreign_customer)
        api.repos.assets.create(foreign_asset)

        api.call("GET", f"/assets/{foreign_asset.asset_id}", expect=404)

    def test_validation(self, api: Api) -> None:
        customer_id = api.customer()["customer_id"]
        path = f"/customers/{customer_id}/assets"
        api.call("POST", path, {"asset_type": "spaceship"}, expect=422)
        api.call("POST", path, {"asset_type": "printer", "business_id": "bus_x"}, expect=422)
        api.call("POST", path, {}, expect=422)


class TestCustomerSearch:
    def test_search_by_name_and_phone_within_the_business(self, api: Api) -> None:
        api.customer(name="Ravi Kumar", phone="90000 20001")
        api.customer(name="Ravi Verma", phone="90000 20002")
        api.customer(name="Meena Iyer", phone="90000 20001")
        api.repos.customers.create(
            make_customer(business_id=OTHER_BUSINESS_ID, name="Ravi Elsewhere", phone="90000 20001")
        )

        by_name = api.call("GET", "/customers?q=ravi", expect=200)
        by_phone = api.call("GET", "/customers?phone=9000020001", expect=200)
        both = api.call("GET", "/customers?phone=90000-20001&q=meena", expect=200)
        everyone = api.call("GET", "/customers", expect=200)

        assert [c["name"] for c in by_name] == ["Ravi Kumar", "Ravi Verma"]
        assert [c["name"] for c in by_phone] == ["Meena Iyer", "Ravi Kumar"]
        assert [c["name"] for c in both] == ["Meena Iyer"]
        assert len(everyone) == 3
