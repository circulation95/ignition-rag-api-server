import asyncio
import types
import unittest
from unittest.mock import patch

from app.tools.opc_tools import read_ignition_tag, write_ignition_tag
from app.tools.sql_tools import db_get_schema, db_list_tables, db_query


class ToolFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_opc_read_write_flow(self):
        class FakeOpcClient:
            async def read_tag(self, tag_path):
                return {"tag": tag_path, "value": 123}

            async def write_tag(self, tag_path, value):
                return {"tag": tag_path, "written": value, "status": "OK"}

        with patch("app.tools.opc_tools.get_opc_client", return_value=FakeOpcClient()):
            read_result = await read_ignition_tag.ainvoke({"tag_path": "[default]Tank/Temp"})
            self.assertEqual(read_result["value"], 123)

            write_result = await write_ignition_tag.ainvoke(
                {"tag_path": "[default]Tank/Setpoint", "value": "50"}
            )
            self.assertEqual(write_result["status"], "OK")

    def test_sql_tool_flow(self):
        class FakeDb:
            def get_table_names(self):
                return ["sqlth_te", "sqlt_data_1_2026_01"]

            def get_table_info(self, table_names):
                return f"schema:{table_names}"

            def run(self, query):
                return f"result:{query}"

        with patch("app.tools.sql_tools.get_sql_db", return_value=FakeDb()):
            tables = db_list_tables.invoke({})
            self.assertIn("sqlth_te", tables)

            schema = db_get_schema.invoke({"table_names": "sqlth_te"})
            self.assertIn("schema", schema)

            result = db_query.invoke({"query": "SELECT 1"})
            self.assertIn("result", result)

            blocked = db_query.invoke({"query": "DELETE FROM sqlth_te"})
            self.assertIn("Read-only", blocked)


if __name__ == "__main__":
    unittest.main()
