# Disaster Recovery & Backup Strategy for Django Multi-Database DBMS

## Overview

This strategy is designed for the existing Django-based multi-database system, where the application database stores user accounts, subscription and payment records, connection metadata, query history, and monitoring/audit artifacts. It is intended for a production-grade deployment beyond the current SQLite development configuration.

The document covers:
- encrypted backup and key management
- point-in-time recovery for logs and audit data
- high availability for the connection abstraction layer
- retention, tiering, and compliance policies
- testable backup integrity without exposing credentials
- cross-region backup distribution
- RTO/RPO targets by component
- backup scheduling compatible with real-time query execution
- consistency during recovery
- recovery runbooks and failure procedures

The strategy is aligned with SOC 2 and GDPR expectations and emphasizes separation of application backup scope from external connected database backup scope.

---

## 1. Encrypted Backup Architecture

### 1.1 Application Database Backup Scope

The application backup scope includes:
- user account records and profile data
- subscription tiers and plan usage
- payment records, invoices, receipts, and billing metadata
- database connection metadata stored in `apps.connections.models.DatabaseConnection`
- query history and query analytics tables
- audit, notification, and monitoring event tables
- workspace and team membership records

This strategy assumes production will use a managed relational backend such as PostgreSQL, MySQL, or a managed cloud DB, not SQLite.

### 1.2 Encryption In Transit and At Rest

Use the database provider and backup toolchain to ensure:
- network encryption for backup transport (TLS/SSL for object storage and DB connections)
- encrypted backup files with FIPS-approved ciphers such as AES-256-GCM
- object storage encryption at rest (SSE-S3, SSE-KMS, or equivalent) for stored backup artifacts
- separate encryption envelope keys for backup archives, not reusing application data keys directly

### 1.3 Credential and Key Storage Architecture

Current code stores external connection passwords encrypted with Fernet via `apps.core.crypto.EncryptionManager` and `ENCRYPTION_KEY` from environment configuration.

For production, replace or augment this with a hardened key-management architecture:
- store the primary encryption key in a managed KMS/secret store (AWS KMS, Azure Key Vault, Google KMS, HashiCorp Vault)
- derive application-level envelope keys from a master key using an HKDF or KDF, such that the application key is not the master key itself
- ensure the DB backup encryption key is itself encrypted under the KMS master key
- use secret rotation policies and KMS access control rather than embedding keys in `.env`

### 1.4 Secure Backup Key Handling

Backup files should be encapsulated in an encrypted envelope with a separate key hierarchy:
- Data Encryption Key (DEK): unique per backup file or backup cohort
- Key Encryption Key (KEK): rotated periodically and managed in KMS
- Wrap each DEK with the KEK; store only encrypted DEKs alongside backup metadata

This allows:
- rotation of KEKs without decrypting existing backup archives
- retention of backup file usability as long as the KEK needed to unwrap the DEK remains available
- destruction of access by revoking KEK or KMS privileges

### 1.5 Key Rotation and Backup Compatibility

Key rotation must be non-destructive:
- maintain a key version metadata field with every backup archive
- when rotating keys, re-wrap existing DEKs under the new KEK, or keep older KEKs online if still needed by retained backups
- use KMS key aliases for current keys and versioned ARNs/IDs for archived backups
- log every rotation event, including who triggered it and why, to a secure audit trail

### 1.6 Preventing Unauthorized Backup Restoration

Ensure backup artifacts cannot be restored without authorized access:
- require KMS decryption rights for both backup archive and DEK envelope metadata
- separate backup access policies from application runtime policies
- enforce MFA, scoped service identities, and least privilege for restore operations
- require explicit restore approvals for critical data categories (payment records, audit logs, connection metadata)

### 1.7 Integration with Existing Encrypted Credential Storage

Existing encrypted credential storage is part of the application database. The strategy should:
- treat `DatabaseConnection.password` as sensitive secret material and not include it in plain backups or logs
- backup the encrypted ciphertext values only, not decrypted passwords
- ensure the KMS that protects backup archive keys is also trusted to protect the application encryption root key
- preserve the ability to decrypt connection credentials after restore only when the restored instance has access to the same encryption root key or a valid key version

---

## 2. Point-in-Time Recovery (PITR) for Audit and Compliance

### 2.1 Separate Log Recovery Procedures

Maintain separate recovery workflows for:
- `connection_logs` / connection metadata change logs
- `query_history` and `query_metrics` tables
- audit trails, user access logs, security events

Each workflow should support targeted restoration to a timestamp or time range with chronological integrity.

### 2.2 Audit Log Forensics and Chronology

For forensic integrity, preserve:
- exact timestamps with timezone normalization
- user identity and session context fields
- source connection identifiers and query IDs
- action type, status, and error context

Recovery procedures must restore logs with original metadata intact. If logs are exported to a separate compliance store, include a metadata schema to reconstruct timelines.

### 2.3 PITR Implementation Model

Use a combined backup model:
- periodic base snapshots of application database state
- continuous transaction log archiving (WAL, binlog, redo logs) for point-in-time recovery
- separate archival of audit/event logs with independent retention policies

PITR for logs should preserve a log stream from the snapshot point to the required timestamp. If logs are stored in separate append-only tables, retain enough history and supporting indexes to query recovered time ranges efficiently.

### 2.4 Validation and Queryability After Recovery

After log recovery, validate that recovered audit and query log tables:
- can be queried by timestamp and user filters
- preserve original created_at/completed_at values
- maintain referential integrity to user and connection entities where applicable
- are included in compliance review queries and SOC 2 evidence generation

### 2.5 Independent Audit Log Recovery

Design audit log recovery to work independently of transactional data recovery by:
- storing audit logs in either a separate database/schema or an audited table set with its own backup chain
- retaining forensic logs even if application data retention is reduced for GDPR compliance, by pseudonymizing or keeping indexable metadata required for audits
- providing a separate restore target and recovery checklist for compliance investigations

---

## 3. High-Availability Replication Strategy

### 3.1 Replicating Connection Metadata and Abstraction Layer

The connection abstraction layer and metadata should be replicated across failover nodes at two levels:
1. database-level replication for `DatabaseConnection`, subscription, user, billing, and audit tables
2. application-level state replication for cache, pool metadata, and active monitoring state

Use a clustered relational database or managed DB service with multi-AZ / read-replica capability.

### 3.2 Handling Primary Failure and Secondary Takeover

Primary failure should trigger a controlled failover path:
- promote a synchronous or semi-synchronous replica to primary for application metadata
- use cluster-aware service discovery or DNS switching to redirect backend processes
- mark the failed node as unhealthy and isolate it from failover decisions

For in-flight queries and connection state:
- record query execution requests and session state in durable queue/storage before dispatch
- avoid relying solely on in-memory session state for failover-critical operations
- if a primary fails mid-query, use idempotent retry semantics on pending query requests and replay requests on the promoted replica when possible

### 3.3 Connection Pool and Active Session Management

Maintain a persistent representation of pool state and active sessions:
- track connection pool leases in a distributed store or database-backed lock table
- capture session heartbeats and request IDs for active query execution
- on failover, allow live sessions to reconnect and optionally continue if the external DB supports session resumption
- if resumption is impossible, fail gracefully with clear user messaging and preserve query history for attempted operations

### 3.4 Real-Time Monitoring Availability and Degradation

Design monitoring so it remains available even under partial failure:
- separate the metrics and monitoring ingestion path from user-facing query execution path
- allow read-only monitoring and query history dashboards to degrade gracefully when write paths are temporarily unavailable
- continue collecting lightweight health metrics with a local buffer and replay once connectivity is restored

### 3.5 Synchronization Trade-offs

Choose replication mode by component:
- synchronous replication for the application database schema that contains connection metadata, subscription status, and payment compliance state when low RPO is essential
- asynchronous or semi-synchronous replication for query history and audit logs, where a small recovery window is acceptable and performance is prioritized
- eventual consistency for real-time monitoring metrics with reconciliation processes to prevent stale dashboard data from masking outages

Trade-offs:
- synchronous replication increases latency and failover complexity, but improves RPO for metadata
- asynchronous replication reduces overhead and supports higher throughput, but requires careful audit of replication lag during incident response

---

## 4. Backup Retention and Tiering Policy

### 4.1 Retention by Subscription Tier

Retention should be aligned to customer tier and compliance requirements:
- **Free tier:** 7 days of data retention, limited query and audit history retention
- **Pro tier:** 30 days retention for application and query data, 90 days for billing and audit metadata if requested
- **Enterprise tier:** 90 days retention for transactional and metadata, 1 year or longer for audit, compliance, and legal hold data

### 4.2 Data Category Retention

Define retention windows per category:
- **User profile and subscription records:** retention until account deletion plus 30 days for reconciliation, unless a legal hold exists
- **Payment/transaction records:** minimum 7 years for PCI/SOC 2 compliance if payments are processed or stored; at least 3 years for audit evidence depending on jurisdiction
- **Connection metadata:** 90 days for free/pro, 365+ days for enterprise and compliance hold accounts
- **Query history:** 7 days for free, 30 days for pro, 90 days for enterprise by default; allow extensions for audit investigations
- **Audit logs / security log data:** 180 days minimum for SOC 2 Type II evidence; 1 year or more for enterprise retention and incident investigations

### 4.3 GDPR and Right-to-Erasure

Apply GDPR-compliant retention controls:
- remove or anonymize personal data on customer deletion requests within required timelines
- retain only pseudonymized audit metadata necessary for compliance and security
- separate operational backup retention from longer-term forensic retention so erasure requests do not inadvertently delete audit evidence required for legal obligations
- ensure backups containing deleted personal data are also subject to erase/pseudonymize policies on restore

### 4.4 Archival and Cold Storage

Implement tiered archival:
- primary fast storage for recent backups needed for PITR and quick recovery
- secondary cold storage for older retention windows and enterprise hold data
- archived backups should remain encrypted and immutable, with separate access controls
- use an audit log for archival lifecycle operations: archive initiation, tier migration, retention expiration, and deletion

### 4.5 Deletion and Compliance Holds

Automate deletion with audit logging:
- scheduled cleanup jobs delete expired backups only after verifying no active legal hold exists
- keep a compliance hold registry for user accounts, investigations, or legal proceedings
- escalation process if a hold conflicts with automated retention deletion
- record deletion events with operator identity, timestamp, and dataset scope

---

## 5. Backup Integrity Testing Without Credential Exposure

### 5.1 Non-production Test Strategy

Test recovery on isolated staging/non-production environments with:
- anonymized or synthetic user records
- masked connection metadata and placeholder credentials
- a separate, non-production copy of the application encryption root key that can decrypt only test data

### 5.2 Integrity Checks

Validate backups using multiple layers:
- cryptographic checksums (SHA-256) for backup archive integrity
- signatures or MACs on backup metadata
- schema validation against the expected production schema
- row counts for key tables before and after restore

### 5.3 Credential Exposure Controls

Ensure testing does not expose plaintext credentials:
- do not inject production `ENCRYPTION_KEY` into test environments
- use a test-only keypair or key hierarchy in staging
- if testing restore of encrypted fields, use synthetic ciphertext generated with the test key
- verify that test restore workflows can unlock backup envelopes without requiring production key access

### 5.4 Referential Integrity Validation

After test restores, verify:
- foreign key constraints in `QueryHistory`, `DatabaseConnection`, `User`, `SubscriptionTier`, and audit tables
- that restore operations preserve `user`, `connection`, and `database` references
- that no orphaned log rows exist unless intentionally preserved as pseudonymized audit records

### 5.5 Encrypted Backup Validation Procedures

Document a standard validation process:
1. decrypt backup envelope using authorized system identity
2. verify archive checksum and signature
3. restore to a sandbox database using a test key hierarchy
4. run automated schema and data integrity checks
5. confirm access only by authorized restore tooling and operator accounts

This testing framework demonstrates restore readiness without requiring production plaintext secrets.

---

## 6. Cross-Region Backup Distribution

### 6.1 Geographic Backup Distribution Model

Use a multi-region backup distribution strategy:
- **Primary region:** active production and near-term backup retention
- **Secondary region:** geographically separate hot/cold copy of encrypted backup archives
- **Tertiary region:** cold or offline copy for extreme disaster recovery

Backup metadata and encrypted archives should be replicated across at least two distinct geographic regions.

### 6.2 Synchronous vs Asynchronous Replication

Classify replication by data criticality:
- **Synchronous or semi-synchronous:** metadata required for failover decisions, encryption key metadata, and manifest records that must not diverge across regions
- **Asynchronous:** actual backup archive replication, query history logs, and archive copies to secondary/tertiary regions

This balances availability and cost. Synchronous cross-region replication for large backup archives is generally too expensive; instead, replicate archive manifests synchronously and archive payloads asynchronously.

### 6.3 Multi-Region Recovery Procedures

When a region is lost:
1. fail over application and backup orchestration to secondary region
2. verify KMS/secret store availability in the secondary region or use cross-region key replicas
3. recover the most recent valid backup archive from the closest available region
4. if secondary region is unavailable, use tertiary archived copies

### 6.4 Dual-Region and Tertiary Protection

Define recovery tiers:
- **Primary/Secondary active backup sites:** used for routine recovery and audits
- **Tertiary cold site:** used when both primary and secondary fail

For tertiary recovery, maintain a separate recovery manifest and periodic validation to ensure cold copies are still readable.

### 6.5 Cost Considerations

Trade-offs include:
- extra storage cost for cross-region copies vs. reduced recovery exposure
- bandwidth cost for asynchronous replication vs. lower RPO
- frequency of secondary region sync vs. total number of archives retained

A practical model is:
- full backup to primary daily
- incremental to secondary hourly or every 4 hours
- tertiary copy weekly for long-term retention

---

## 7. RTO and RPO Targets by Component

| Component | RPO | RTO | Notes |
|---|---|---|---|
| User accounts / subscription records | 15 min (enterprise), 1 hour (pro), 4 hours (free) | 30 min (enterprise), 2 hrs (pro), 6 hrs (free) | Metadata must be highly available for login, billing, and entitlement enforcement |
| Connection metadata / credentials | 15 min (enterprise), 1 hour (pro), 4 hours (free) | 30 min (enterprise), 2 hrs (pro), 6 hrs (free) | Failover of connection abstractions is critical for resumed external queries |
| Query history / query logs | 1 hour (enterprise), 4 hours (pro), 24 hours (free) | 2 hrs (enterprise), 6 hrs (pro), 24 hrs (free) | Logs are compliance-relevant but can tolerate slight delay |
| Payment / transaction records | 5 min (enterprise), 15 min (pro), 1 hr (free) | 30 min (enterprise), 1 hr (pro), 4 hrs (free) | Compliance-driven; should use strongest persistence and audit trail |
| Audit logs / forensic data | 5 min ingest lag, retention per policy | 2 hrs recovery, 1 business day for extended evidence | Must enable SOC 2 Type II evidence and support investigations |

### 7.1 How Targets Drive Architecture

- low RPO for metadata means using synchronous or semi-synchronous replication for key tables and transaction logs
- moderate RPO for query history allows asynchronous log shipping and deferred archival
- low RTO for payments and subscriptions requires automated failover and validated restore operations
- audit log targets require separate retention and restore pipelines to avoid coupling with user deletion cycles

---

## 8. Backup Scheduling and Real-Time Compatibility

### 8.1 Backup Types and Timing

Use a hybrid schedule:
- **daily full backups** outside peak hours, ideally during the lowest user activity window
- **hourly incremental backups** for application metadata and high-value tables
- **continuous log archiving** for transaction logs and audit streams
- **weekly or monthly long-term archives** for enterprise compliance retention

### 8.2 Minimizing Impact on Live Query Execution

Design backups to avoid interfering with real-time queries:
- use DB-native snapshot or incremental backup mechanisms instead of table locks
- avoid long-running logical dumps during peak hours
- throttle backup I/O based on system load and query latency metrics
- isolate backup I/O from main query I/O paths using dedicated storage or network lanes when possible

### 8.3 Consistency with Concurrent Queries

Maintain consistency by using:
- database snapshots at a consistent transaction boundary
- WAL/binlog archiving to preserve changes during backup windows
- application-level quiesce only when absolutely necessary for metadata schema changes

This ensures queries executed during backups still complete normally, and the backup represents a coherent point-in-time.

### 8.4 Load-aware Scheduling

Adapt scheduling based on usage:
- shift full backups to off-peak time windows automatically when load exceeds thresholds
- run incremental backups more frequently during low-traffic periods
- schedule validation and restore rehearsals in staging when production load is highest,
- postpone or throttle non-critical archival operations during peak business hours

### 8.5 Backup Job Monitoring

Integrate backup jobs into the monitoring stack so failures and slowdowns trigger alerts before they affect recovery windows.
- monitor job duration, I/O wait, and backup throughput
- alert when backup completion slips past its window
- correlate backup health with query latency and active user sessions

---

## 9. Data Consistency During Recovery

### 9.1 Transactional Consistency Across Application and Connected Databases

Because external connected databases are managed by third parties or customer-owned systems, the product should:
- maintain the application DB as the source of truth for metadata and session state
- treat external DB data as outside the application backup scope, while preserving connection references and metadata
- coordinate recovery with external DB owners when a full integrated restore is required

### 9.2 Referential Integrity Post-Restore

During restore operations, verify:
- foreign keys linking `QueryHistory`, `QueryExecutionMetric`, `DatabaseConnection`, `User`, and `ManagedDatabase` are intact
- relational table sets such as subscription, payment, and user authorization tables restore with compatible IDs
- associated audit log references resolve correctly to the restored user and connection records

### 9.3 Handling Mixed Point-in-Time Restores

If tables are restored to different points:
- tag recovered snapshots with recovery timestamps and origin identifiers
- avoid restoring dependent tables from drastically different points unless the relationship is reconstructed
- when necessary, use compensated reconciliation scripts to repair orphaned references or remove invalid log entries

### 9.4 Connection Metadata Validation

After recovery, validate connection metadata against the actual external connections by:
- checking stored host/port/engine metadata for expected values
- optionally running authenticated reachability tests with masked credentials
- confirming that credential ciphertext can be decrypted using the authorized key material and that metadata matches the external DB selection state

### 9.5 Query History and Log Validity

After restoring logs, ensure:
- recovered query history rows still reference valid users and connections where possible
- orphaned log entries are flagged for review if the referenced connection or user no longer exists
- audit logs retain enough context for compliance without exposing deleted personal data beyond what is permitted

---

## 10. Recovery Runbooks and Failure Scenarios

### 10.1 Recovering from Application Database Corruption

1. identify the corruption scope using monitoring, DB health checks, and integrity validation
2. isolate the corrupted instance and fail traffic to the secondary replica if available
3. select the latest valid backup and transaction log segment consistent with the corruption point
4. decrypt and restore the backup archive into a sandbox environment
5. run schema and referential integrity checks
6. promote the recovery instance after validation and bring application services back online
7. verify login, subscription, and connection metadata access
8. sign off with an incident checklist and update the recovery audit log

### 10.2 Recovering from Loss of a Connected Database Connection

1. preserve historical query records and audit logs related to the lost connection
2. do not perform a full application restore unless the metadata store itself is affected
3. restore connection metadata and credential ciphertext from the latest backup if the connection record is lost
4. revalidate the restored connection by testing reachability with decrypted credentials in a controlled environment
5. if the external DB itself is lost, request the external database owner’s backup/restore procedure and reconcile records with restored metadata
6. keep query history intact even if the external connection is recreated under a new identifier

### 10.3 Table-level or Range Recovery Without Full System Restore

1. identify the affected table(s) and time range
2. restore the relevant table(s) from a recent full backup or PITR stream into a sandbox database
3. run schema and FK checks on the restored subset
4. export the corrected rows and import them into production using controlled migration scripts
5. mark imported rows with a recovery audit tag and log the operation

### 10.4 Failover to Secondary Region

**Planned failover:**
- perform readiness checks on the secondary region
- synchronize the latest backup manifest and key metadata
- switch service discovery and DNS to secondary endpoints
- verify application and monitoring services are operational
- drain the primary region if possible and preserve logs for reconciliation

**Unplanned failover:**
- detect regional outage through health checks and backup alarms
- automatically promote the nearest healthy replica with valid configuration
- activate cross-region backup recovery if the primary region cannot be restored quickly
- notify stakeholders and begin restore validation immediately

### 10.5 Validation and Sign-off Procedures

After recovery, execute the following validation steps:
- confirm user login and subscription enforcement
- verify connection metadata load and external connectivity sampling
- validate payment records and billing state against source data
- run audit log queries for the recovered timeframe
- compare restored row counts against backup metadata
- obtain sign-off from operations, security/compliance, and product owner

### 10.6 Communication and Escalation

Define incident severity levels and communication expectations:
- **Severity 1:** production outage affecting all users; immediate on-call escalation, status page update, executive notification
- **Severity 2:** degraded functionality for a subset of users or metadata; incident response team notification within 15 minutes
- **Severity 3:** backup or restore test failure without current production impact; ticket creation and remediation owner assignment

Escalation responsibilities:
- operations team: own failover execution and infrastructure recovery
- security/compliance: approve audit log recovery and legal hold decisions
- engineering: support restore scripts, schema validation, and integration checks
- customer success: communicate tier-specific recovery expectations to affected customers

---

## Additional Considerations

### Roles and Responsibilities

- **Platform/Operations:** manage backup pipelines, key rotation, cross-region distribution, failover automation, archive deletion
- **Security/Compliance:** define retention, legal hold, SOC 2 evidence preservation, GDPR erasure controls
- **Database/Infrastructure:** provision and monitor managed DB replication, storage, and region failover
- **Engineering:** integrate backup-compatible storage layout, metadata audit logging, and restore validation tooling
- **Support/Customer Success:** communicate recovery expectations by subscription tier and maintain SLAs

### CAP Theorem Trade-offs

This system prioritizes availability for real-time monitoring and query execution while maintaining strong consistency for metadata and audit-critical state. The strategy uses:
- consistency-first replication for connection metadata and billing state
- availability-oriented asynchronous log shipping for query/audit histories
- partition-tolerant archive copies across regions to survive outages

### Monitoring and Alerting Integration

Integrate backup health into monitoring by tracking:
- backup success/failure counts and completion latency
- encryption key rotation and KMS access errors
- restore test outcomes and integrity validation failures
- replication lag and failover event metrics

Alerting should be configured for:
- missed backup windows
- checksum/signature validation failures
- KMS permission anomalies and key lifecycle events
- cross-region replication interruptions

### Cost Implications

Costs are influenced by:
- backup storage volume and retention length
- cross-region transfer and storage for secondary/tertiary copies
- replication mode and synchronous bandwidth usage
- additional failover infrastructure and validation environments

Optimization guidance:
- reserve synchronous replication only for the smallest high-value metadata set
- use asynchronous log shipping for larger audit and query archives
- archive older backups to cold storage and delete expired data automatically
- align tiered retention costs with customer tiers and compliance pricing

---

## Summary

This strategy provides a production-ready blueprint for securing backups, restoring audit-compliant timelines, and maintaining resilience across regional failures. It preserves the existing encrypted credential pattern while upgrading key management for SOC 2 and GDPR compliance, separates application metadata from external DB recovery, and defines realistic RTO/RPO targets by component.

The next step is to formalize this into operational runbooks and implement a managed backup/KMS architecture with staged restore validations.
