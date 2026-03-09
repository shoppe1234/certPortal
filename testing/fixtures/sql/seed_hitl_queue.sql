-- testing/fixtures/sql/seed_hitl_queue.sql
-- Seeds two hitl_queue rows: one to approve (PAM-02), one to reject.
-- Safe to re-run — ON CONFLICT DO NOTHING.
-- Reset: DELETE FROM hitl_queue WHERE queue_id IN ('test-queue-approve', 'test-queue-reject');

INSERT INTO hitl_queue (
    queue_id, retailer_slug, supplier_slug, agent,
    draft, summary, channel, thread_id, status
)
VALUES
    (
        'test-queue-approve',
        'lowes', 'acme',
        'monica',
        'Dear Acme team, your 850 PO-TEST-850 has been processed successfully. '
        'All required segments validated. Gate 1 is now COMPLETE.',
        'Approval pending for acme Gate 1 completion message',
        'email',
        'thread-test-001',
        'PENDING_APPROVAL'
    ),
    (
        'test-queue-reject',
        'lowes', 'acme',
        'monica',
        'Dear Acme team, please resubmit your 850 with corrected BEG03 (max 22 chars). '
        'Current value exceeds the Lowe''s specification limit.',
        'Rejection candidate — correction request for oversized PO number',
        'email',
        'thread-test-002',
        'PENDING_APPROVAL'
    )
ON CONFLICT (queue_id) DO NOTHING;
