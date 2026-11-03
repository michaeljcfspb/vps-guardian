-- =============================================================================
-- VPS Guardian — bootstrap do MySQL (executar como administrador do MySQL)
--
-- Objetivo: criar banco e usuário de aplicação com privilégio MÍNIMO (PRD §8.3).
-- NÃO versione senhas reais: troque os placeholders abaixo no momento da execução
-- e guarde a senha apenas no gerenciador de segredos do Easypanel.
--
-- Banco: MySQL 8.0+ (necessário para JSON, colunas geradas e SKIP LOCKED).
-- =============================================================================

-- 1) Banco exclusivo ----------------------------------------------------------
CREATE DATABASE IF NOT EXISTS `vps_guardian`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

-- 2) Usuário da aplicação ------------------------------------------------------
--    'localhost' cobre o acesso via socket; em rede privada use o host interno
--    (ex.: 'guardian'@'10.0.0.%'). Evite '%' aberto para a internet.
CREATE USER IF NOT EXISTS 'guardian'@'%' IDENTIFIED BY 'TROCAR_POR_SENHA_FORTE';

-- 3) Privilégios mínimos: apenas DML/DDL no próprio banco ---------------------
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP
    ON `vps_guardian`.* TO 'guardian'@'%';

-- Necessário para o Alembic registrar a versão do schema.
GRANT CREATE TEMPORARY TABLES ON `vps_guardian`.* TO 'guardian'@'%';

FLUSH PRIVILEGES;

-- 4) Verificações pós-criação -------------------------------------------------
SELECT VERSION() AS mysql_version;
SELECT @@character_set_database AS charset, @@collation_database AS collation;
SHOW GRANTS FOR 'guardian'@'%';

-- Observações:
--   * O usuário NÃO recebe privilégios globais (sem SUPER, FILE, PROCESS, GRANT).
--   * A porta 3306 nunca deve ser publicada; o acesso é pela rede privada.
--   * Para o banco de testes (CI/VPS), repita criando `vps_guardian_test`.
