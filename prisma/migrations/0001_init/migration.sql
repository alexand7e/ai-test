CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE "UserLevel" AS ENUM ('NORMAL', 'ADMIN', 'ADMIN_GERAL');

CREATE TABLE IF NOT EXISTS "Grupo" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "nome" TEXT NOT NULL,
    "descricao" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Grupo_pkey" PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "Usuario" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "email" TEXT NOT NULL,
    "senhaHash" TEXT NOT NULL,
    "nivel" "UserLevel" NOT NULL DEFAULT 'NORMAL',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "grupoId" UUID NOT NULL,
    CONSTRAINT "Usuario_pkey" PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "Agente" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "nome" TEXT NOT NULL,
    "configuracoes" JSONB NOT NULL,
    "vetorEmbedding" vector(1536),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "grupoId" UUID NOT NULL,
    "criadoPorId" UUID NOT NULL,
    CONSTRAINT "Agente_pkey" PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "AccessToken" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "jti" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuarioId" UUID NOT NULL,
    CONSTRAINT "AccessToken_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "Agente" ALTER COLUMN "vetorEmbedding" TYPE vector(1536);

CREATE INDEX IF NOT EXISTS "Grupo_nome_idx" ON "Grupo"("nome");

CREATE UNIQUE INDEX IF NOT EXISTS "Usuario_email_key" ON "Usuario"("email");
CREATE INDEX IF NOT EXISTS "Usuario_grupoId_idx" ON "Usuario"("grupoId");
CREATE INDEX IF NOT EXISTS "Usuario_nivel_idx" ON "Usuario"("nivel");

CREATE INDEX IF NOT EXISTS "Agente_grupoId_idx" ON "Agente"("grupoId");
CREATE INDEX IF NOT EXISTS "Agente_criadoPorId_idx" ON "Agente"("criadoPorId");
CREATE INDEX IF NOT EXISTS "Agente_vetorEmbedding_hnsw_idx" ON "Agente" USING hnsw ("vetorEmbedding" vector_cosine_ops) WHERE "vetorEmbedding" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "AccessToken_jti_key" ON "AccessToken"("jti");
CREATE INDEX IF NOT EXISTS "AccessToken_usuarioId_idx" ON "AccessToken"("usuarioId");
CREATE INDEX IF NOT EXISTS "AccessToken_expiresAt_idx" ON "AccessToken"("expiresAt");

ALTER TABLE "Usuario" ADD CONSTRAINT "Usuario_grupoId_fkey" FOREIGN KEY ("grupoId") REFERENCES "Grupo"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Agente" ADD CONSTRAINT "Agente_grupoId_fkey" FOREIGN KEY ("grupoId") REFERENCES "Grupo"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Agente" ADD CONSTRAINT "Agente_criadoPorId_fkey" FOREIGN KEY ("criadoPorId") REFERENCES "Usuario"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "AccessToken" ADD CONSTRAINT "AccessToken_usuarioId_fkey" FOREIGN KEY ("usuarioId") REFERENCES "Usuario"("id") ON DELETE CASCADE ON UPDATE CASCADE;
