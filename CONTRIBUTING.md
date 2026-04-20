# Contribuindo

Obrigado por considerar contribuir com o Meta Chat Exporter.

## Antes de abrir uma issue

- Verifique se o problema ou sugestão já não existe nas issues abertas.
- Sempre que possível, descreva o contexto, os passos para reproduzir e o resultado esperado.
- Se o problema envolver arquivos exportados pela Meta, remova dados sensíveis antes de compartilhar exemplos.

## Preparando o ambiente local

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Rodando os testes

```bash
pytest -q
```

Se a sua mudança alterar comportamento visível, atualize ou adicione testes junto com a implementação.

## Diretrizes de contribuição

- Prefira mudanças pequenas e focadas.
- Preserve o estilo do código já existente.
- Atualize a documentação quando a interface, o fluxo ou a CLI mudarem.
- Não inclua arquivos gerados localmente como `config.json`, `.chat_export_cache/`, logs ou exportações de teste.

## Enviando um pull request

Antes de abrir o PR, confirme:

- que a branch está atualizada com a base do repositório;
- que os testes passam localmente;
- que a descrição do PR explica o problema resolvido e a abordagem escolhida;
- que você incluiu screenshots ou exemplos, quando a mudança afetar a GUI ou o HTML exportado.

## Escopo das contribuições

Contribuições para parser, exportadores, interface, testes, documentação e automação do projeto são bem-vindas.