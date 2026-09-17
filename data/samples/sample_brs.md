# Business Requirements Specification — MediTrack Patient Portal

## 1. Background

Sunrise Clinics operates eleven outpatient centres and currently manages patient
appointments through phone calls and a shared spreadsheet. Staff report roughly
40 minutes per day per centre spent on rescheduling, and patients have no way to
see their own records. The board has approved a project to deliver a patient-facing
web portal and a matching staff console.

## 2. Business goals

- Reduce appointment no-show rates by at least 20% within two quarters of launch.
- Cut administrative time spent on appointment handling by half.
- Give patients self-service access to appointments, prescriptions and test results.
- Provide clinic managers with utilisation reporting across all eleven centres.

## 3. Stakeholders

- Patients (primary end users, approximately 48,000 active records)
- Front-desk administrators at each centre
- Clinicians (doctors, nurse practitioners)
- Clinic operations managers
- The information governance officer

## 4. In scope

- Patients must be able to register an account and verify their identity by email and SMS.
- The system shall allow patients to book, reschedule and cancel appointments online.
- The system must send appointment reminders 48 hours and 2 hours before the appointment.
- Patients shall be able to view their prescription history and download test results as PDF.
- Clinicians must be able to view a daily schedule and mark appointments as completed or missed.
- The staff console shall provide a utilisation report per centre per week.
- The system must integrate with the existing LabConnect results feed over HL7.
- All access to patient records must be logged with actor, action and timestamp.
- The portal must support English and Marathi.
- Patient data must be encrypted at rest and in transit.
- The system shall maintain 99.5% uptime during clinic operating hours.
- Page responses must complete within 2 seconds for 95% of requests under normal load.
- The system must support 500 concurrent users at peak.

## 5. Out of scope

- Video consultation and telemedicine features.
- Billing, insurance claims and payment processing.
- Native mobile applications (the portal must be responsive on mobile browsers instead).
- Integration with the legacy PACS imaging system.

## 6. Constraints

- The solution must comply with applicable health data protection regulations.
- The project budget is capped and the first release must ship within six months.
- The clinic's existing identity provider must be used for staff login via SSO.
- Hosting must remain within the country for data residency reasons.

## 7. Business and process requirements

- Front-desk staff shall be trained on the new console before each centre goes live.
- A patient-facing user guide must be published in both supported languages.
- The information governance officer must sign off the data protection impact assessment before launch.
- A rollback and communication plan must be agreed with clinic managers prior to each rollout.
- Vendor contracts for SMS delivery must be finalised by the procurement team.

## 8. Assumptions

- Patient contact details in the existing spreadsheet are accurate enough to migrate.
- LabConnect will continue to expose its current HL7 interface for at least two years.
- Each centre has reliable broadband during operating hours.

## 9. Open questions

- What is the required retention period for audit logs? TBD with governance.
- Should cancelled appointments be automatically offered to a waiting list?
- Which appointment types can be booked without triage? To be decided by clinical leads.
