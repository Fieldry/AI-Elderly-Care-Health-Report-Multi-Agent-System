from __future__ import annotations

import unittest

from tests.api_flows.support import APIFlowTestCase


class DoctorApiFlowTestCase(APIFlowTestCase):
    def test_doctor_can_view_all_elderly_and_manage_followups(self):
        elderly_one = self._start_chat()
        elderly_two = self._start_chat()

        self._save_session_profile(
            elderly_one["accessToken"],
            elderly_one["sessionId"],
            {
                "age": 82,
                "sex": "女",
                "residence": "城市",
                "living_arrangement": "独居",
                "hypertension": "是",
                "diabetes": "是",
            },
        )

        report_one = self._generate_report_for_elderly(
            elderly_one["userId"],
            elderly_one["accessToken"],
            payload={
                "age": 82,
                "sex": "女",
                "residence": "城市",
                "living_arrangement": "独居",
                "hypertension": "是",
                "diabetes": "是",
            },
        )
        report_two = self._generate_report_for_elderly(
            elderly_two["userId"],
            elderly_two["accessToken"],
            payload={
                "age": 79,
                "sex": "男",
                "residence": "农村",
                "arthritis": "是",
            },
        )
        original_profile = self.conversation_manager.store.get_profile(elderly_one["userId"])

        doctor_login = self._login_doctor()
        self.assertEqual(doctor_login["role"], "doctor")
        doctor_token = doctor_login["token"]

        elderly_list = self.client.get(
            "/doctor/elderly-list",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(elderly_list.status_code, 200, elderly_list.text)
        list_body = elderly_list.json()["data"]
        returned_ids = {item["elderly_id"] for item in list_body}
        self.assertIn(elderly_one["userId"], returned_ids)
        self.assertIn(elderly_two["userId"], returned_ids)
        first_overview = next(item for item in list_body if item["elderly_id"] == elderly_one["userId"])
        self.assertGreaterEqual(first_overview["session_count"], 1)
        self.assertGreaterEqual(first_overview["report_count"], 1)
        self.assertEqual(first_overview["management"]["management_status"], "normal")

        sessions = self.client.get(
            "/api/sessions",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(sessions.status_code, 200, sessions.text)
        returned_user_ids = {item["user_id"] for item in sessions.json()["sessions"]}
        self.assertIn(elderly_one["userId"], returned_user_ids)
        self.assertIn(elderly_two["userId"], returned_user_ids)

        session_detail = self.client.get(
            f"/api/sessions/{report_one['sessionId']}",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(session_detail.status_code, 200, session_detail.text)
        self.assertEqual(session_detail.json()["metadata"]["user_id"], elderly_one["userId"])

        doctor_detail = self.client.get(
            f"/doctor/elderly/{elderly_one['userId']}",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(doctor_detail.status_code, 200, doctor_detail.text)
        detail_body = doctor_detail.json()
        self.assertEqual(detail_body["elderly_id"], elderly_one["userId"])
        self.assertEqual(detail_body["reports"][0]["id"], report_one["reportId"])
        self.assertEqual(detail_body["followups"], [])

        followup_response = self.client.post(
            f"/doctor/elderly/{elderly_one['userId']}/followups",
            json={
                "visitType": "电话",
                "findings": "近一周夜间起身增多，家属反馈步态较前变慢。",
                "recommendations": ["两周内复评步态", "提醒家属加强夜间照护"],
                "contactedFamily": True,
                "arrangedRevisit": True,
                "referred": False,
                "nextFollowupAt": "2026-04-05T10:00:00",
                "notes": "建议继续观察夜间如厕风险",
            },
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(followup_response.status_code, 200, followup_response.text)
        self.assertEqual(followup_response.json()["visit_type"], "电话")

        management_response = self.client.patch(
            f"/doctor/elderly/{elderly_one['userId']}/management",
            json={
                "isKeyCase": True,
                "managementStatus": "priority_follow_up",
                "contactedFamily": True,
                "arrangedRevisit": True,
                "referred": False,
                "nextFollowupAt": "2026-04-05T10:00:00",
            },
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(management_response.status_code, 200, management_response.text)
        self.assertTrue(management_response.json()["is_key_case"])
        self.assertEqual(
            management_response.json()["management_status"],
            "priority_follow_up",
        )

        followups = self.client.get(
            f"/doctor/elderly/{elderly_one['userId']}/followups",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(followups.status_code, 200, followups.text)
        self.assertEqual(len(followups.json()["data"]), 1)

        updated_detail = self.client.get(
            f"/doctor/elderly/{elderly_one['userId']}",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(updated_detail.status_code, 200, updated_detail.text)
        updated_body = updated_detail.json()
        self.assertEqual(updated_body["management"]["management_status"], "priority_follow_up")
        self.assertEqual(updated_body["followups"][0]["visit_type"], "电话")

        shared_report = self.client.get(
            f"/report/{report_one['reportId']}",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(shared_report.status_code, 200, shared_report.text)
        self.assertEqual(shared_report.json()["summary"], "整体情况需要持续观察。")

        another_report = self.client.get(
            f"/report/{report_two['reportId']}",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(another_report.status_code, 200, another_report.text)

        latest_profile = self.conversation_manager.store.get_profile(elderly_one["userId"])
        self.assertEqual(original_profile.age, latest_profile.age)
        self.assertEqual(original_profile.sex, latest_profile.sex)
        self.assertEqual(original_profile.hypertension, latest_profile.hypertension)

    def test_doctor_is_read_only_on_sessions_and_report_generation(self):
        elderly = self._start_chat()
        doctor_login = self._login_doctor()
        doctor_token = doctor_login["token"]

        save_profile = self.client.post(
            f"/api/sessions/{elderly['sessionId']}/profile",
            json={"age": 88},
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(save_profile.status_code, 403)

        delete_session = self.client.delete(
            f"/api/sessions/{elderly['sessionId']}",
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(delete_session.status_code, 403)

        generate_with_session = self.client.post(
            "/report/generate",
            json={
                "sessionId": elderly["sessionId"],
                "profile": {"age": 88, "sex": "男"},
            },
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(generate_with_session.status_code, 403)

        generate_for_elderly = self.client.post(
            f"/report/generate/{elderly['userId']}",
            json={"age": 88, "sex": "男"},
            headers=self._auth_headers(doctor_token),
        )
        self.assertEqual(generate_for_elderly.status_code, 403)


if __name__ == "__main__":
    unittest.main()
