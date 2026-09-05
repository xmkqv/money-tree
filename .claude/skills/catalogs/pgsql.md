[pgsql][pgsql]
    18 is current; rls semantics below are unchanged since 9.5
    rls: policies split into using over existing rows and with check over new rows
        using filters; a row failing it is invisible, never an error
        with check raises 42501 "new row violates row-level security policy"
        insert and the update post-image go through with check, so denial is loud
        update and delete select their targets through using, so denial is silent
        an update denied by using reports 0 rows and succeeds
        an update whose where or returning reads columns also needs the select policy using
        insert on conflict do update is the one exception: a using failure on the existing row raises
        row_security = off turns any policy-filtered query into an error, for backups and audits
        no builtin reports which policy denied a row
    [plpgsql][plpgsql]
        found and get diagnostics row_count both read 0 for a denied row and for an absent row
        neither can reconstruct a denial, so a post-hoc row count is not a permission check
        a returns void function swallows the whole distinction at the call boundary
        the deterministic pattern is a definer predicate raised before the write
        raise insufficient_privilege emits 42501, matching what with check would have raised
    definer: security definer runs policies of the owner, not the caller
        a definer predicate reads scope tables the caller cannot select
        set search_path = '' is required on definer bodies to close the resolution hole
        stable definer predicates are inlined into policy quals and cached per statement
    trg: row triggers fire per affected row, so a 0-row update fires nothing
        an audit or revision trigger is therefore blind to a policy-filtered write
        statement triggers still fire, and see no rows in their transition tables
    [cte][cte]
        side-effect-free ctes can be folded into the parent query
        materialized and not materialized make the optimization boundary explicit
        recursive ctes express bounded graph and hierarchy traversal
    [json][json]
        jsonb_to_record and jsonb_to_recordset convert objects to typed rows
        json_table converts nested sql/json values to relational rows
    [ord][ord]
        with ordinality attaches a stable one-based position to set-returning output
    [upsert][upsert]
        on conflict provides an atomic insert-or-update outcome
        unique-index inference survives replacement by an equivalent index
        one do-update statement cannot affect the same target row more than once
    [merge][merge]
        postgresql 18 merge supports matched, not-matched, and by-source actions
        returning exposes the action plus old and new target values
    [pg19b3][pg19b3]
        postgresql 19 beta 3 was released on 2026-08-13
        group by all was reverted before beta 3
        beta releases are not suitable for production

## refs

[pgsql]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
[plpgsql]: https://www.postgresql.org/docs/current/plpgsql-statements.html
[cte]: https://www.postgresql.org/docs/current/queries-with.html
[json]: https://www.postgresql.org/docs/current/functions-json.html
[ord]: https://www.postgresql.org/docs/current/functions-srf.html
[upsert]: https://www.postgresql.org/docs/current/sql-insert.html
[merge]: https://www.postgresql.org/docs/current/sql-merge.html
[pg19b3]: https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/
