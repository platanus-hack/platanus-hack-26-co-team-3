# landing-page

Bloque 8 (idea.md): la página pública de Roxy, orientada a equipos que corren
flujos de agentes.

HTML y CSS planos, un solo archivo. Sin build, sin dependencias, sin
framework: se abre con doble clic y se despliega copiando la carpeta a
cualquier hosting estático (Vercel, Netlify, S3, GitHub Pages).

```bash
python3 -m http.server 5192   # y abrir http://localhost:5192
```

## Decisiones

- **Modo claro y oscuro** por `prefers-color-scheme`, sin toggle: sigue al
  sistema de quien la abra.
- **Responsive** de 360px para arriba.
- El **comando de instalación en el hero** (`pip install roxy-guard`) y el
  bloque de código son deliberados: la audiencia es gente que integra, y lo
  primero que quiere saber es qué tan invasivo es. La respuesta es una línea.
- Las cifras del hero llevan su fuente al pie. Salen de `research/`, no son
  inventadas.
