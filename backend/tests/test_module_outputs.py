from fastapi.testclient import TestClient

from app.main import app

H = {"x-user-role": "md"}


def test_module_output_save_get_and_upsert():
    with TestClient(app) as c:
        deal_id = c.post("/api/v1/deals", headers=H, json={"deal_name": "Persist Test Deal"}).json()["id"]

        # Save an M6 output.
        r1 = c.put(f"/api/v1/deals/{deal_id}/module-output", headers=H,
                   json={"module_key": "m6_lbo", "payload": {"equity_irr": 0.43, "moic": 6.1}})
        assert r1.status_code == 200

        # Save an M7 output.
        c.put(f"/api/v1/deals/{deal_id}/module-output", headers=H,
              json={"module_key": "m7_regulatory", "payload": {"filings_required": 1}})

        # Upsert the M6 output (should not create a duplicate).
        c.put(f"/api/v1/deals/{deal_id}/module-output", headers=H,
              json={"module_key": "m6_lbo", "payload": {"equity_irr": 0.51, "moic": 7.0}})

        outputs = c.get(f"/api/v1/deals/{deal_id}/module-outputs", headers=H).json()["outputs"]
        assert set(outputs.keys()) == {"m6_lbo", "m7_regulatory"}
        assert outputs["m6_lbo"]["payload"]["equity_irr"] == 0.51  # upserted value


def test_module_output_unknown_deal_404():
    with TestClient(app) as c:
        r = c.get("/api/v1/deals/does-not-exist/module-outputs", headers=H)
        assert r.status_code == 404
