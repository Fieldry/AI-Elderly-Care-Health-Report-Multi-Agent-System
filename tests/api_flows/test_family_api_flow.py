from __future__ import annotations

import unittest

from tests.api_flows.support import APIFlowTestCase


class FamilyApiFlowTestCase(APIFlowTestCase):
    def test_family_bound_elderly_full_api_flow(self):
        elderly_one = self._start_chat()
        elderly_two = self._start_chat()

        register_body, phone, password = self._register_family(elderly_one["userId"])
        self.assertEqual(register_body["role"], "family")
        self.assertEqual(register_body["elderly_ids"], [elderly_one["userId"]])

        family_token = register_body["token"]
        bind_response = self.client.post(
            "/auth/family/bind",
            json={
                "elderlyId": elderly_two["userId"],
                "relation": "配偶",
            },
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(bind_response.status_code, 200, bind_response.text)
        self.assertEqual(bind_response.json(), {"success": True})

        login_response = self.client.post(
            "/auth/login",
            json={"phone": phone, "password": password},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        login_body = login_response.json()
        self.assertEqual(set(login_body["elderly_ids"]), {elderly_one["userId"], elderly_two["userId"]})

        family_token = login_body["token"]
        elderly_list = self.client.get(
            "/family/elderly-list",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(elderly_list.status_code, 200, elderly_list.text)
        self.assertEqual(
            {item["elderly_id"] for item in elderly_list.json()["data"]},
            {elderly_one["userId"], elderly_two["userId"]},
        )

        update_response = self.client.put(
            f"/family/elderly/{elderly_one['userId']}",
            json={
                "name": "王阿姨",
                "age": 81,
                "sex": "女",
                "residence": "城市",
                "living_arrangement": "与子女同住",
                "hypertension": "是",
            },
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        self.assertEqual(update_response.json(), {"success": True})

        elderly_detail = self.client.get(
            f"/family/elderly/{elderly_one['userId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(elderly_detail.status_code, 200, elderly_detail.text)
        detail_profile = elderly_detail.json()["profile"]
        self.assertEqual(detail_profile["age"], 81)
        self.assertEqual(detail_profile["sex"], "女")
        self.assertEqual(detail_profile["hypertension"], "是")

        start_session = self.client.post(
            f"/family/session/start/{elderly_one['userId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(start_session.status_code, 200, start_session.text)
        start_body = start_session.json()
        self.assertEqual(start_body["elderly_id"], elderly_one["userId"])
        self.assertEqual(start_body["state"], "GREETING")
        family_session_id = start_body["session_id"]

        family_message = self.client.post(
            f"/family/session/{family_session_id}/message",
            json={"content": "我是她女儿，最近走路慢了，也更需要照看。"},
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(family_message.status_code, 200, family_message.text)
        family_message_body = family_message.json()
        self.assertEqual(family_message_body["state"], "COLLECTING")
        self.assertEqual(family_message_body["progress"], 0.0)

        family_info = self.client.get(
            f"/family/session/{family_session_id}/info",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(family_info.status_code, 200, family_info.text)
        family_info_body = family_info.json()
        self.assertEqual(family_info_body["elderly_id"], elderly_one["userId"])
        self.assertEqual(family_info_body["state"], "COLLECTING")

        report_response = self._generate_report_for_elderly(
            elderly_one["userId"],
            family_token,
            payload={
                "age": 81,
                "sex": "女",
                "residence": "城市",
                "hypertension": "是",
                "living_arrangement": "与子女同住",
            },
        )
        self.assertEqual(report_response["report"]["summary"], "整体情况需要持续观察。")
        report_id = report_response["reportId"]
        report_session_id = report_response["sessionId"]

        family_reports = self.client.get(
            f"/family/reports/{elderly_one['userId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(family_reports.status_code, 200, family_reports.text)
        self.assertEqual([item["id"] for item in family_reports.json()["data"]], [report_id])

        shared_report = self.client.get(
            f"/report/{report_id}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(shared_report.status_code, 200, shared_report.text)
        self.assertEqual(shared_report.json()["summary"], "整体情况需要持续观察。")

        family_sessions = self.client.get(
            "/api/sessions",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(family_sessions.status_code, 200, family_sessions.text)
        visible_session_ids = {item["session_id"] for item in family_sessions.json()["sessions"]}
        self.assertIn(elderly_one["sessionId"], visible_session_ids)
        self.assertIn(elderly_two["sessionId"], visible_session_ids)
        self.assertIn(report_session_id, visible_session_ids)

        session_detail = self.client.get(
            f"/api/sessions/{report_session_id}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(session_detail.status_code, 200, session_detail.text)
        self.assertEqual(session_detail.json()["metadata"]["user_id"], elderly_one["userId"])

        logout_response = self.client.post("/auth/logout")
        self.assertEqual(logout_response.status_code, 200, logout_response.text)
        self.assertEqual(logout_response.json(), {"success": True})

    def test_family_cannot_access_unbound_elderly_resources(self):
        elderly_one = self._start_chat()
        elderly_two = self._start_chat()
        register_body, _, _ = self._register_family(elderly_one["userId"])
        family_token = register_body["token"]

        other_report = self._generate_report_for_elderly(
            elderly_two["userId"],
            elderly_two["accessToken"],
            payload={
                "age": 85,
                "sex": "男",
                "residence": "农村",
            },
        )

        forbidden_detail = self.client.get(
            f"/family/elderly/{elderly_two['userId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(forbidden_detail.status_code, 403)

        forbidden_start = self.client.post(
            f"/family/session/start/{elderly_two['userId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(forbidden_start.status_code, 403)

        forbidden_reports = self.client.get(
            f"/family/reports/{elderly_two['userId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(forbidden_reports.status_code, 403)

        forbidden_session = self.client.get(
            f"/api/sessions/{other_report['sessionId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(forbidden_session.status_code, 403)

        forbidden_report = self.client.get(
            f"/report/{other_report['reportId']}",
            headers=self._auth_headers(family_token),
        )
        self.assertEqual(forbidden_report.status_code, 403)


if __name__ == "__main__":
    unittest.main()
