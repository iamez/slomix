"""Transaction-owned receipt reservation shared by all canonical import callers."""


async def claim_import_receipt(
    adapter, filename: str, *, source_sha256: str | None = None,
    require_linked_parent: bool = False,
) -> None:
    """Reserve/lock the receipt until the caller's transaction commits or aborts.

    Must run inside the SAME transaction as the following receipt read, data
    writes and completion update. Preserve an existing aggregate flag, including
    NULL, and all metadata. A new FALSE row is invisible until commit and rolls
    back with a failed import. ON CONFLICT also locks already-existing rows.
    At repeatable-read/serializable isolation a conflicting stale snapshot can
    fail; callers must retry the entire transaction, never ignore that failure.

    The key deliberately matches the legacy filename receipt, not file content.
    This does not protect changed content, alternate names or older importers
    that do not participate in this protocol.
    """
    if require_linked_parent:
        if source_sha256 is None:
            raise ValueError('Strict parent receipt requires a source digest')
        await adapter.execute(
            """INSERT INTO proximity_processed_files
                   (filename, aggregates_applied, file_hash, runtime_parent_gate)
               VALUES (?, FALSE, ?, TRUE)
               ON CONFLICT (filename) DO UPDATE SET
                   aggregates_applied = proximity_processed_files.aggregates_applied""",
            (filename, source_sha256),
        )
        row = await adapter.fetch_one(
            'SELECT runtime_parent_gate FROM proximity_processed_files WHERE filename = ?',
            (filename,),
        )
        if row is None or row[0] is not True:
            raise ValueError('Existing receipt lacks strict parent provenance')
        return
    if source_sha256 is not None:
        # Only new rows receive a digest. Never stamp current bytes onto an old
        # receipt whose earlier imported content is unknown.
        await adapter.execute(
            """INSERT INTO proximity_processed_files (filename, aggregates_applied, file_hash)
               VALUES (?, FALSE, ?)
               ON CONFLICT (filename) DO UPDATE SET
                   aggregates_applied = proximity_processed_files.aggregates_applied""",
            (filename, source_sha256),
        )
        return
    await adapter.execute(
        """INSERT INTO proximity_processed_files (filename, aggregates_applied)
           VALUES (?, FALSE)
           ON CONFLICT (filename) DO UPDATE SET
               aggregates_applied = proximity_processed_files.aggregates_applied""",
        (filename,),
    )
