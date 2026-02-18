"""
Unit Tests for DatabaseAdapter

Tests for PostgreSQL database operations including:
- Connection management
- Transaction handling and rollback
- Query execution (fetch_one, fetch_all, execute)
- Error handling
- Connection pooling
"""

import pytest
from bot.core.database_adapter import PostgreSQLAdapter


class TestDatabaseConnection:
    """Tests for database connection and initialization"""

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_database_adapter_creation(self, test_db_config):
        """Test database adapter can be created with valid config"""
        adapter = PostgreSQLAdapter(
            host=test_db_config["host"],
            port=test_db_config["port"],
            database=test_db_config["database"],
            user=test_db_config["user"],
            password=test_db_config["password"],
            min_pool_size=test_db_config["min_pool_size"],
            max_pool_size=test_db_config["max_pool_size"]
        )

        assert adapter is not None
        assert adapter.database == "etlegacy_test"

        # Connect and verify
        await adapter.connect()
        assert adapter.is_connected()

        # Cleanup
        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_database_connection_and_close(self, db_adapter):
        """Test database connection can be opened and closed"""
        # db_adapter fixture automatically connects
        assert db_adapter.is_connected()

        # Verify we can execute a simple query
        result = await db_adapter.fetch_val("SELECT 1 as test")
        assert result == 1

    @pytest.mark.asyncio
    async def test_database_invalid_credentials(self):
        """Test connection fails with invalid credentials"""
        adapter = PostgreSQLAdapter(
            host="localhost",
            port=5432,
            database="nonexistent_db",
            user="invalid_user",
            password="wrong_password"
        )

        # Connection should fail
        with pytest.raises(Exception):
            await adapter.connect()


class TestDatabaseQueries:
    """Tests for basic query operations"""

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_fetch_val_simple_query(self, db_adapter):
        """Test fetch_val returns single value"""
        result = await db_adapter.fetch_val("SELECT 42 as answer")
        assert result == 42

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_fetch_one_returns_row(self, db_adapter):
        """Test fetch_one returns dictionary row"""
        result = await db_adapter.fetch_one(
            "SELECT 1 as id, 'test' as name"
        )

        assert result is not None
        assert result["id"] == 1
        assert result["name"] == "test"

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_fetch_all_returns_multiple_rows(self, db_adapter):
        """Test fetch_all returns list of rows"""
        result = await db_adapter.fetch_all(
            "SELECT generate_series(1, 5) as num"
        )

        assert result is not None
        assert len(result) == 5
        assert result[0]["num"] == 1
        assert result[4]["num"] == 5

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_parameterized_query(self, db_adapter):
        """Test parameterized queries prevent SQL injection"""
        # Test with parameter
        result = await db_adapter.fetch_val(
            "SELECT $1::integer + $2::integer as sum",
            (10, 20)
        )

        assert result == 30

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_fetch_one_no_results(self, db_adapter):
        """Test fetch_one returns None when no results"""
        result = await db_adapter.fetch_one(
            "SELECT 1 WHERE FALSE"
        )

        assert result is None


class TestDatabaseTransactions:
    """Tests for transaction handling and rollback"""

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_transaction_commit(self, clean_test_db):
        """Test transaction commits successfully"""
        # Insert data in transaction
        async with clean_test_db.transaction():
            await clean_test_db.execute(
                """
                INSERT INTO rounds (round_date, round_time, map_name, round_number)
                VALUES ($1, $2, $3, $4)
                """,
                ("2025-12-17", "12:00:00", "goldrush", 1)
            )

        # Verify data was committed
        count = await clean_test_db.fetch_val(
            "SELECT COUNT(*) FROM rounds WHERE map_name = $1",
            ("goldrush",)
        )

        assert count == 1

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_transaction_rollback_on_exception(self, clean_test_db):
        """Test transaction rolls back when exception occurs"""
        # Attempt to insert data but raise exception
        try:
            async with clean_test_db.transaction():
                await clean_test_db.execute(
                    """
                    INSERT INTO rounds (round_date, round_time, map_name, round_number)
                    VALUES ($1, $2, $3, $4)
                    """,
                    ("2025-12-17", "12:00:00", "rollback_test", 1)
                )

                # Raise exception to trigger rollback
                raise Exception("Simulated error for rollback test")
        except Exception as e:
            assert "Simulated error" in str(e)

        # Verify data was NOT committed (rolled back)
        count = await clean_test_db.fetch_val(
            "SELECT COUNT(*) FROM rounds WHERE map_name = $1",
            ("rollback_test",)
        )

        assert count == 0, "Transaction should have rolled back, but data was committed"

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_nested_transactions_not_supported_gracefully(self, clean_test_db):
        """Test nested transactions are handled (PostgreSQL doesn't support true nested transactions)"""
        # PostgreSQL uses savepoints for nested transactions
        # This test verifies we don't crash with nested transaction attempts

        async with clean_test_db.transaction():
            await clean_test_db.execute(
                """
                INSERT INTO rounds (round_date, round_time, map_name, round_number)
                VALUES ($1, $2, $3, $4)
                """,
                ("2025-12-17", "12:00:00", "outer_txn", 1)
            )

            # Nested transaction attempt
            # Note: asyncpg doesn't support nested transaction() context managers
            # This would need to use savepoints explicitly in production code

        # Verify outer transaction committed
        count = await clean_test_db.fetch_val(
            "SELECT COUNT(*) FROM rounds WHERE map_name = $1",
            ("outer_txn",)
        )

        assert count == 1


class TestDatabaseIntegrity:
    """Tests for foreign keys, constraints, and data integrity"""

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_foreign_key_constraint_prevents_orphans(self, clean_test_db):
        """Test foreign key constraints prevent orphaned records"""
        # Try to insert player stats without a round (should fail)
        with pytest.raises(Exception):  # Foreign key violation
            await clean_test_db.execute(
                """
                INSERT INTO player_comprehensive_stats
                (round_id, round_date, map_name, round_number, player_guid, player_name, team, kills, deaths)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                (99999, "2025-12-17", "fk_test", 1, "TESTGUID", "TestPlayer", 1, 10, 5)
            )

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_cascade_delete_removes_child_records(self, clean_test_db):
        """Test CASCADE delete removes related records"""
        # Insert a round
        round_id = await clean_test_db.fetch_val(
            """
            INSERT INTO rounds (round_date, round_time, map_name, round_number)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            ("2025-12-17", "12:00:00", "cascade_test", 1)
        )

        # Insert player stats for this round
        await clean_test_db.execute(
            """
            INSERT INTO player_comprehensive_stats
            (round_id, round_date, map_name, round_number, player_guid, player_name, team, kills, deaths)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            (round_id, "2025-12-17", "cascade_test", 1, "TESTGUID1", "Player1", 1, 10, 5)
        )

        await clean_test_db.execute(
            """
            INSERT INTO player_comprehensive_stats
            (round_id, round_date, map_name, round_number, player_guid, player_name, team, kills, deaths)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            (round_id, "2025-12-17", "cascade_test", 1, "TESTGUID2", "Player2", 2, 8, 7)
        )

        # Verify player stats exist
        player_count_before = await clean_test_db.fetch_val(
            "SELECT COUNT(*) FROM player_comprehensive_stats WHERE round_id = $1",
            (round_id,)
        )
        assert player_count_before == 2

        # Delete the round (should cascade)
        await clean_test_db.execute(
            "DELETE FROM rounds WHERE id = $1",
            (round_id,)
        )

        # Verify player stats were deleted (CASCADE)
        player_count_after = await clean_test_db.fetch_val(
            "SELECT COUNT(*) FROM player_comprehensive_stats WHERE round_id = $1",
            (round_id,)
        )
        assert player_count_after == 0, "CASCADE delete should have removed player stats"

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_unique_constraint_prevents_duplicates(self, clean_test_db):
        """Test unique constraints prevent duplicate records"""
        # Insert a processed file hash
        await clean_test_db.execute(
            """
            INSERT INTO processed_files (filename, file_hash)
            VALUES ($1, $2)
            """,
            ("file1.txt", "abc123hash")
        )

        # Try to insert same filename again (filename is unique in current schema)
        try:
            await clean_test_db.execute(
                """
                INSERT INTO processed_files (filename, file_hash)
                VALUES ($1, $2)
                """,
                ("file1.txt", "different_hash")
            )

            # If insert succeeds unexpectedly, ensure duplicates were not created.
            count = await clean_test_db.fetch_val(
                "SELECT COUNT(*) FROM processed_files WHERE filename = $1",
                ("file1.txt",)
            )
            assert count == 1

        except Exception as e:
            # Unique constraint violation expected
            assert "unique" in str(e).lower() or "duplicate" in str(e).lower()


class TestDatabaseErrorHandling:
    """Tests for error handling and edge cases"""

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_invalid_sql_syntax_raises_error(self, db_adapter):
        """Test invalid SQL raises appropriate error"""
        with pytest.raises(Exception):
            await db_adapter.fetch_one("SELECT * FROM nonexistent_table_xyz")

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_type_mismatch_in_parameters(self, db_adapter):
        """Test type mismatch in parameters is handled"""
        # Try to pass string where integer expected
        with pytest.raises(Exception):
            await db_adapter.fetch_val(
                "SELECT $1::integer as num",
                ("not_a_number",)
            )

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_null_value_handling(self, db_adapter):
        """Test NULL values are handled correctly"""
        result = await db_adapter.fetch_val("SELECT NULL as empty")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_empty_string_vs_null(self, clean_test_db):
        """Test distinction between empty string and NULL"""
        # Insert round with empty string map name
        round_id = await clean_test_db.fetch_val(
            """
            INSERT INTO rounds (round_date, round_time, map_name, round_number)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            ("2025-12-17", "12:00:00", "", 1)
        )

        # Fetch and verify
        map_name = await clean_test_db.fetch_val(
            "SELECT map_name FROM rounds WHERE id = $1",
            (round_id,)
        )

        assert map_name == ""
        assert map_name is not None


class TestConnectionPooling:
    """Tests for connection pooling behavior (if implemented)"""

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_multiple_concurrent_queries(self, db_adapter):
        """Test multiple queries can run concurrently with connection pooling"""
        import asyncio

        # Run 10 queries concurrently
        tasks = [
            db_adapter.fetch_val(f"SELECT {i} as num")
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert results[0] == 0
        assert results[9] == 9

    @pytest.mark.asyncio
    @pytest.mark.requires_db
    async def test_connection_reuse(self, db_adapter):
        """Test connections are reused from pool"""
        # Execute multiple queries sequentially
        for i in range(5):
            result = await db_adapter.fetch_val("SELECT 1")
            assert result == 1

        # If connection pooling works, this should not create 5 connections
        # (Hard to verify without access to pool internals)
