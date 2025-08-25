# Automação DOM Natal/RN — Scraper + API

Este projeto automatiza a coleta, armazenamento e gestão de dados do Diário Oficial do Município de Natal/RN (DOM). Ele consiste em um scraper para extrair informações e uma API para gerenciar os metadados dos arquivos.

## Funcionalidades

* **Coleta de Dados:** Raspa edições do Diário Oficial de Natal/RN.
* **Armazenamento de PDFs:** Baixa os arquivos PDF de cada edição.
* **Upload e Publicação:** Envia os PDFs para o serviço `0x0.st`, obtendo URLs públicas para acesso direto.
* **Persistência de Metadados:** Salva os metadados dos arquivos (como URL e data de publicação) em um banco de dados PostgreSQL.
* **API de Gestão:** Disponibiliza uma API REST com o framework FastAPI para listar, sincronizar e importar arquivos do DOM.

## 💻 Tecnologias Utilizadas

* **Python**
* **FastAPI:** Para a construção da API.
* **httpx** (download/upload assíncrono)
* **Pydantic** v2 Para validação e anotações
* **Selenium:** Para a automação do scraping.
* **PostgreSQL:** Para o banco de dados.
* **Docker & Docker Compose:** Para a orquestração dos serviços e facilidade de execução.

## Como Executar o Projeto (Com Docker)

Para rodar o projeto localmente, siga os passos abaixo:

### Pré-requisitos

Certifique-se de que o [Docker](https://www.docker.com/) e o [Docker Compose](https://docs.docker.com/compose/install/) estejam instalados em sua máquina.

### Configuração do Ambiente

1.  Clone este repositório:
    ```bash
    git clone [https://github.com/edurs2602/automacao-selenium](https://github.com/edurs2602/automacao-selenium)
    cd automacao-selenium
    ```
2.  Crie um arquivo `.env` na raiz do projeto, utilizando o `.env.example` como modelo.
3.  Preencha as variáveis de ambiente necessárias. Um exemplo mínimo de configuração do Selenium é:
    ```env
    SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
    ```
4. Crie um diretorio na raiz do projeto chamada data e dentro dele crie um chamado dom
    ```bash
    mkdir data/dom
    ```

### Iniciar os Serviços

Execute o seguinte comando para subir todos os containers:

```bash
docker-compose up -d --build
```

O comando `--build` garantirá que as imagens dos containers sejam construídas a partir do código mais recente. O flag `-d` executa os containers em segundo plano.

Agora com os serviços funcionando, de o seguinte comando em outra instancia do terminial para fazer que o selenium rode o scraper

```bash
docker compose run --rm app
```

## Uso da API

Após iniciar os serviços, a API estará acessível em `http://localhost:8000`.

Você pode acessar a documentação interativa da API (gerada pelo FastAPI/Swagger UI) em:

`http://localhost:8000/docs`

## Pontos de melhorias futuros

- Resiliência do scraper: seletores ainda mais tolerantes a mudanças no DataTables; fallbacks adicionais.

- Tarefas assíncronas: orquestração com Celery/Arq/APScheduler para agendar sincronizações mensais automáticas.

- Observabilidade: métricas e traces (Prometheus/OpenTelemetry) e dashboards.

- Validação e deduplicação: checksum (SHA256) e upsert mais robusto com índices únicos.

- Segurança: autenticação (JWT) e rate limiting na API.

- Testes automatizados: unitários e end-to-end (pytest + Playwright/Selenium).

- CI/CD: pipeline para build, testes e deploy automático; imagens multi-arquitetura.

- Paginação/ordenação na API /files e filtros extras (tipo: “extra”, “especial”).
