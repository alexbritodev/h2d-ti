# Banco de produção. O script de inicialização vai DENTRO da imagem porque, no deploy pelo
# Portainer, bind mount com caminho relativo não funciona: os arquivos do stack não existem no
# host, e o Docker cria uma pasta vazia no lugar do arquivo.
# O contexto de build é a raiz do repositório.
FROM pgvector/pgvector:pg17
COPY --chmod=755 infra/db/init/01-databases.sh /docker-entrypoint-initdb.d/01-databases.sh
