from app.domain.models import Flow


def buyer_seller_flow() -> Flow:
    return Flow.model_validate(
        {
            "id": "flow_test",
            "name": "Buyer seller routing",
            "description": "A test flow",
            "trigger": {"type": "new_contact_message", "description": "a contact messages us", "config": {}},
            "start_node_id": "ask_role",
            "nodes": [
                {"id": "ask_role", "type": "ask_question", "message": "Buyer or seller?", "variable": "role", "options": ["Buyer", "Seller"], "next_node_id": "check_role"},
                {"id": "check_role", "type": "condition", "variable": "role", "operator": "equals", "value": "Buyer", "true_node_id": "assign_sales", "false_node_id": "send_help"},
                {"id": "assign_sales", "type": "assign_team", "team_name": "Sales", "team_id": "team_1", "next_node_id": "buyer_end"},
                {"id": "send_help", "type": "send_message", "message": "Help article", "next_node_id": "seller_end"},
                {"id": "buyer_end", "type": "end"},
                {"id": "seller_end", "type": "end"},
            ],
        }
    )
