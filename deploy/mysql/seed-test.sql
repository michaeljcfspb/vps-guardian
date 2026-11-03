-- =============================================================================
-- ATENÇÃO: ARQUIVO DE TESTE — NÃO EXECUTAR EM PRODUÇÃO
--
-- Dados fictícios apenas para validar o painel/API em ambiente de homologação.
-- Não contém usuários nem credenciais: o administrador é criado pela CLI
-- (`python -m app.cli create-admin`) e os tokens de agente são gerados pela API.
--
-- Pré-requisito: `alembic upgrade head` já aplicado.
-- Remoção completa: DELETE FROM servers WHERE name LIKE 'TESTE-%';
-- =============================================================================

INSERT INTO `servers` (
    id, name, hostname, ip_address, environment, provider, region, panel,
    tags, notes, collection_interval_seconds, heartbeat_timeout_seconds,
    status, created_at, updated_at
) VALUES
    (
        '11111111-1111-4111-8111-111111111111',
        'TESTE-Easypanel-01', 'teste-easypanel-01.local', '203.0.113.11',
        'staging', 'teste', 'br-sp', 'easypanel',
        JSON_ARRAY('teste', 'easypanel'), 'Servidor fictício de homologação',
        30, 90, 'unprovisioned', UTC_TIMESTAMP(), UTC_TIMESTAMP()
    ),
    (
        '22222222-2222-4222-8222-222222222222',
        'TESTE-Portainer-01', 'teste-portainer-01.local', '203.0.113.12',
        'staging', 'teste', 'br-sp', 'portainer',
        JSON_ARRAY('teste', 'portainer'), 'Servidor fictício de homologação',
        30, 90, 'unprovisioned', UTC_TIMESTAMP(), UTC_TIMESTAMP()
    )
ON DUPLICATE KEY UPDATE
    hostname = VALUES(hostname),
    updated_at = UTC_TIMESTAMP();

-- Configurações padrão usadas pelas fases seguintes (retenção e notificações).
INSERT INTO `system_settings` (`key`, `value`, `updated_at`) VALUES
    ('retention', JSON_OBJECT('raw_days', 7, 'agg_5m_days', 30, 'agg_1h_days', 180), UTC_TIMESTAMP()),
    ('notifications', JSON_OBJECT('enabled', false, 'min_severity', 'warning'), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
    `value` = VALUES(`value`),
    `updated_at` = UTC_TIMESTAMP();

SELECT id, name, panel, status FROM `servers` WHERE name LIKE 'TESTE-%';
