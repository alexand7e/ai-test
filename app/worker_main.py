import asyncio
import logging

from app.core.container import Container
from app.core.worker import Worker

logger = logging.getLogger(__name__)

# Arquitetura
#
# API e Worker compartilham 100% das dependências
# Um único ponto de configuração (Container)
# Consistência
# Mesmos agentes
# Mesmo Redis
# Mesmo Qdrant
# Mesmo Prisma
# Escalabilidade
# Todos usando o mesmo modelo
#
async def main():
    container = await Container.create()

    worker = Worker(container)
    try:
        await worker.start()
    finally:
        await container.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

