# Scientific conversation P0: generic client boundary

The protected backend can return a completed `EvidenceAssessmentReceipt` for an
owner-scoped saved scientific result. Studio displays this receipt in the existing
Assistant and preserves the scientific workspace. Receipt rendering does not
submit a Q&A or numerical job. The client contains no assessment/planning physics.

The capability catalog now accepts `availability="unavailable"` with a safe
`availability_reason`; scientific registration alone does not mean its backend
dependency is executable. Existing `active` responses remain compatible.

Focused validation: 22 tests passed across `test_studio_evidence_assessment.py`,
`test_studio_scientific.py`, `test_scientific_availability_contract.py` and
`test_studio_request.py`. This covers one execution across rerenders, context and
previous-result preservation, receipt history/composer behavior and wire contracts.

The coordinated private `fix/scientific-conversation-p0` branch contains source
verification, interpretation and bounded evidence assessment. Real authenticated
Studio/Bedrock/SAGE-AVO acceptance evidence belongs in that private repository.
No model algorithms, deployment, authentication or storage changes are introduced.
