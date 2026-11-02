"""Forward-only parent evidence under the canonical import's receipt row lock.

Requires migration096 and the same transaction as source binding/child writes.
This does not discover parents, repair history, or namespace source filenames.
"""


async def validate_receipt_parent(adapter, filename: str, round_id: int) -> None:
    """Refuse reassignment and adoption of completed receipts without a link."""
    row = await adapter.fetch_one(
        'SELECT linked_round_id, aggregates_applied FROM proximity_processed_files WHERE filename = ?',
        (filename,),
    )
    if row is None:
        raise RuntimeError('Proximity round binding requires a claimed receipt')
    linked, completed = row
    if linked is None and completed is True:
        raise ValueError('Existing completed proximity receipt lacks durable round identity')
    if linked is not None and linked != round_id:
        raise ValueError('Proximity receipt conflicts with recorded round identity')


async def record_receipt_parent(adapter, filename: str, round_id: int) -> None:
    """Bind after parser success and repeated parent/context validation.

No commit here. Failure/cancellation of the outer transaction must roll back
the link together with the source digest, completion receipt and child data.
"""
    row = await adapter.fetch_one(
        '''UPDATE proximity_processed_files SET linked_round_id = ?
           WHERE filename = ? AND runtime_parent_gate = TRUE
             AND aggregates_applied = TRUE AND file_hash IS NOT NULL
             AND (linked_round_id IS NULL OR linked_round_id = ?)
           RETURNING linked_round_id''',
        (round_id, filename, round_id),
    )
    if row is None or row[0] != round_id:
        raise RuntimeError('Proximity receipt round binding was not recorded')
