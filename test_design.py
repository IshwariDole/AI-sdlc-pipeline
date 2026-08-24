from app.design.generator import generate_design
from app.models.schemas import ClassifiedSRS


def test_design():

    classified_srs = ClassifiedSRS(
        project_name="Test Authentication System",
        classifications=[
            {
                "id": "FR-001",
                "text": "Users shall be able to register and login securely.",
                "type": "Technical",
                "subcategory": "Backend",
                "reasoning": "User authentication requires backend APIs, business logic, and security implementation."
            },
            {
                "id": "FR-002",
                "text": "The system shall store user account information.",
                "type": "Technical",
                "subcategory": "Database",
                "reasoning": "Storing user information requires database schema design and persistence logic."
            },
            {
                "id": "FR-003",
                "text": "The system shall provide a responsive login interface.",
                "type": "Technical",
                "subcategory": "Frontend",
                "reasoning": "A responsive interface requires frontend engineering and UI implementation."
            },
            {
                "id": "FR-004",
                "text": "A user manual shall be provided.",
                "type": "Non-Technical",
                "subcategory": "Documentation",
                "reasoning": "Creating documentation does not require implementation of a software system component."
            }
        ]
    )

    result = generate_design(
        classified=classified_srs,
        project_name="Test Authentication System"
    )

    print("\n===== DESIGN GENERATED SUCCESSFULLY =====\n")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    test_design()