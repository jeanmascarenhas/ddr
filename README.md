# Agente de IA Generativa para Consultas SQL em Sistemas ERP

Projeto desenvolvido no contexto de um **Trabalho de Conclusão de Curso (TCC)**, com o objetivo de investigar a utilização de **Agentes de Inteligência Artificial Generativa** para realização de consultas a dados em sistemas **Enterprise Resource Planning (ERP)** por meio de linguagem natural e consultas SQL.

O estudo busca avaliar se a utilização de um agente capaz de interpretar solicitações em linguagem natural, gerar consultas SQL e recuperar informações diretamente da base de dados de um ERP pode **reduzir o tempo e a complexidade da busca por informações**, quando comparada à utilização tradicional das interfaces e telas do sistema.

## Objetivo

Desenvolver e avaliar um agente de IA Generativa capaz de:

* interpretar perguntas realizadas em linguagem natural;
* identificar as informações solicitadas pelo usuário;
* gerar consultas SQL correspondentes;
* executar as consultas sobre a base de dados do ERP;
* apresentar os resultados de forma compreensível ao usuário.

## Tecnologias

* **Odoo Community** — ERP utilizado como ambiente experimental;
* **PostgreSQL** — banco de dados relacional;
* **Python** — linguagem de desenvolvimento;
* **LangChain** — orquestração do agente de IA;
* **Google Gemini** — modelo de linguagem;
* **Chainlit** — interface conversacional;
* **Docker** — conteinerização e gerenciamento do ambiente.

## Abordagem

A arquitetura proposta utiliza uma interface conversacional para receber as solicitações do usuário. O agente de IA interpreta a pergunta, gera uma consulta SQL adequada à estrutura do banco de dados do ERP e executa a consulta para obter os dados solicitados.

A avaliação do projeto considera aspectos como **tempo de obtenção da informação, precisão das consultas, complexidade da interação e segurança na execução das consultas**, permitindo comparar a abordagem baseada em linguagem natural com a utilização convencional das interfaces do ERP.

## Estrutura do Projeto

O projeto é organizado de forma a separar a **interface conversacional**, a **API responsável pela lógica do agente** e os componentes relacionados ao ambiente do ERP e banco de dados.

> Este repositório possui finalidade acadêmica e experimental, sendo desenvolvido para investigação da aplicação de Inteligência Artificial Generativa em sistemas ERP.
