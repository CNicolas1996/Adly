# Tech Advisor

Tu asesor técnico permanente. No una herramienta — un **rol**.

---

## ¿Qué es esto?

Es un sistema de 6 playbooks + 1 referencia técnica que convierten a Claude en un **staff engineer + tech lead + project manager senior** disponible 24/7 para tus proyectos.

No es un validador. No es una checklist. Es un **asesor** al que le tocas la puerta cuando lo necesites — sea para arrancar algo nuevo, revisar cómo va lo que tienes, decidir entre opciones técnicas, preparar un lanzamiento, limpiar código feo, u optimizar lo que está caro/lento.

---

## ¿Por qué existe?

Porque Claude por defecto valida demasiado.

Le dices "quiero hacer X" y te dice "qué buena idea, aquí tienes el código". Eso está bien para tareas chiquitas, pero **mata proyectos serios** — porque arrancas a codear sin haber pensado en arquitectura, riesgos, o si lo que vas a construir tiene sentido siquiera.

Este sistema cambia esa dinámica:
- Te **filtra** antes de construir
- Te **detecta scope creep** mientras construyes
- Te **dice no-go** cuando estás listo para "lanzar pero no tanto"
- Te **prioriza deuda crítica** sobre features nuevas
- Te **llama el efecto Chavo** cuando aparece (idea overload, sobreingeniería, procrastinación premium)

El principio: **calidad > velocidad**. No es para entregar más rápido. Es para no construir mierda.

---

## ¿Cómo funciona?

### 1. Instalas el skill
Subes la carpeta `tech-advisor/` como Claude Skill (Settings → Capabilities → Skills → Upload).

### 2. Hablas normal
Cuando hables de un proyecto técnico, Claude detecta automáticamente cuál de los 6 modos aplica según lo que digas:

```
Tú: "Quiero hacer un scraper de leads de LinkedIn"
Claude: → carga playbook 01_arrancar.md y empieza el flujo
```

```
Tú: "¿Postgres o SQLite para esto?"
Claude: → carga playbook 03_consulta_rapida.md y responde directo
```

```
Tú: "Adly está caro, gasto mucho en LLM calls"
Claude: → carga playbook 06_optimizar.md y empieza diagnóstico
```

### 3. Claude ejecuta el playbook
Cada playbook tiene pasos, preguntas y output esperado. Claude te lleva a través del proceso. No improvisa, sigue el método.

### 4. Sales con decisiones, no con dudas
Cada playbook tiene un cierre claro: lo que quedó decidido, próximos pasos concretos.

---

## Los 6 modos (qué hace cada uno)

### 🚀 Modo 1 — ARRANCAR
**Cuándo:** vas a empezar algo nuevo
**Preguntas como:** "Quiero hacer X", "voy a construir Y", "estoy pensando en Z"
**En 5-10 min sales con:** arquetipo claro, stack elegido, top 3 riesgos, próximos pasos, GO/NO-GO
**Lo que evita:** vibe code arranque sin plan, escoger stack por hype, scope inflado desde el día 1

### 🩺 Modo 2 — HEALTH CHECK
**Cuándo:** llevas tiempo en un proyecto y dudas del rumbo
**Preguntas como:** "¿Cómo voy?", "siento que ando perdido", "¿estoy en scope creep?"
**En 10-15 min sales con:** semáforo (verde/amarillo/rojo), diagnóstico honesto, decisión de continuar/pivotar/pausar/matar, plan de los próximos 7 días
**Lo que evita:** proyectos zombies que nunca mueren ni avanzan, scope creep silencioso, drift sin diagnóstico

### ⚡ Modo 3 — CONSULTA RÁPIDA
**Cuándo:** tienes UNA pregunta técnica concreta
**Preguntas como:** "¿Postgres o SQLite?", "¿qué patrón uso?", "¿vale la pena Redis?"
**En 2-5 min sales con:** recomendación clara + razón en 2-3 puntos + cuándo cambiarías de opinión
**Lo que evita:** respuestas tipo "depende de muchas cosas", listas de 5 opciones sin opinar

### 🎯 Modo 4 — GET READY FOR
**Cuándo:** quieres saltar a otra fase (idea→MVP, MVP→alpha, alpha→beta, beta→prod, prod→escala)
**Preguntas como:** "Voy a lanzar a Camí", "está listo para producción", "voy a abrirlo a 50 users"
**En 15-20 min sales con:** gap analysis vs la fase target, refactor roadmap si hay deuda crítica, decisión GO/NO-GO/condicional
**Lo que evita:** lanzar algo medio listo y quemar usuarios, "casi" cuando el target es "estable"

### 🧹 Modo 5 — REFACTOR
**Cuándo:** el código está feo y quieres limpiarlo
**Preguntas como:** "Esto está enredado", "ya no entiendo mi código", "ayúdame a refactorizar"
**En 15-20 min sales con:** diagnóstico (cuántos smells, qué tipo), tipo de refactor (parcial/estructural/rewrite/dejar), plan ordenado por riesgo, criterio medible de éxito
**Lo que evita:** rewrites que mueren a la mitad, refactor sin tests previos, refactor por aburrimiento disfrazado de mejora

### 🚀 Modo 6 — OPTIMIZAR
**Cuándo:** algo está lento, caro, consumiendo mucho, o no escala
**Preguntas como:** "Está lento", "pierdo plata en LLM calls", "se cae con N users"
**En 10-15 min sales con:** baseline medido (no asumido), causa raíz identificada, top 1-2 optimizaciones por ROI, target medible
**Lo que evita:** optimizar sin medir, microoptimizaciones que no son el bottleneck, "está lento" sin número

---

## El séptimo archivo: Patterns Library

`07_patterns_library.md` no es un playbook — es la **referencia técnica** que los demás playbooks consultan cuando necesitan info específica de un arquetipo (Agent, CLI, API, Pipeline, Web App, Game).

Tú no abres este archivo directo. Los otros playbooks lo invocan cuando lo necesitan ("para Agent, ver 07_patterns_library.md sección Agent").

---

## Ejemplos de uso real (cómo se ve en práctica)

### Ejemplo A — Arrancar un side project

```
Tú: "Tengo ganas de hacer una herramienta CLI que parsee mis emails de Gmail
     y me genere un resumen diario."

Claude: [carga 01_arrancar.md]
        Antes de stack o código — filtro brutal:
        1. ¿Para quién es? ¿Tú o más gente?
        2. ¿Qué pasa si NO lo construyes? ¿Cuál es el dolor real hoy?
        3. ¿Por qué AHORA? ¿Hay urgencia o es la idea del momento?

Tú: "Es para mí, el dolor es que pierdo 30 min al día en Gmail, ahora porque
     llevo 2 meses pateándolo."

Claude: OK, filtro pasado. Vamos a las 10 preguntas críticas...
        [continúa el playbook]
        
        Final:
        - Arquetipo: CLI + Pipeline (lite)
        - Stack: Python + Typer + Gmail API + LLM provider
        - Top 3 riesgos: OAuth de Gmail, costo LLM si emails son largos, parseo de threads
        - Testing: snapshot de output con emails de prueba
        - Próximos 3 pasos: setup OAuth Gmail, prototipo de fetch de N emails, llamada LLM con 1 email
        - GO ✅
```

### Ejemplo B — Health check de Adly

```
Tú: "No sé cómo voy con Adly, siento que llevo dando vueltas."

Claude: [carga 02_health_check.md]
        Antes de evaluar dónde estás, recordemos dónde dijiste que ibas:
        1. ¿Cuál era el problema original?
        2. ¿Quién era el usuario? (Camí, ¿verdad?)
        3. ¿Qué prometiste y para cuándo?
        4. ¿Cuántas semanas llevas?

[continúa el flujo]

        Diagnóstico:
        - Semáforo: 🟡 amarillo
        - Problema 1: scope creep moderado (4 nuevas features no planeadas)
        - Problema 2: deuda crítica acumulada (system prompt verbose + sin tests core)
        - Decisión recomendada: PAUSAR features, pagar deuda 2 semanas, reanclar
        - Acción próximas 24h: bloquear cualquier feature nueva, abrir engine.py
```

### Ejemplo C — Consulta rápida en medio de codear

```
Tú: "Estoy haciendo el cache de Adly, ¿in-memory LRU o Redis?"

Claude: [carga 03_consulta_rapida.md]
        Una pregunta antes: ¿Adly corre en 1 sola máquina o ya pensaste
        que vaya en server compartido?

Tú: "1 sola máquina, instalación local de Camí."

Claude: → in-memory LRU (functools.lru_cache o cachetools).
        Razón: 1 proceso, 1 máquina, no necesitas red ni infra extra.
        Cuándo cambiar de opinión: cuando lo migres a server con >1 worker
        o quieras compartir cache entre usuarios.
```

---

## ¿Cuándo NO usar este sistema?

- ❌ Cuando solo quieres que Claude **escriba código** (no consultoría)
- ❌ Cuando preguntas conceptuales aisladas ("¿qué es REST?")
- ❌ Cuando estás en otro dominio (música, escritura, idiomas)
- ❌ Cuando el "asesor" se vuelve excusa para no codear (procrastinación premium)
- ❌ Cuando ya tomaste la decisión y solo buscas validación (eso no es consulta, es apoyo emocional)

---

## ¿Qué pasa si necesito mezclar 2 modos?

Sí pasa. Ejemplo: arrancas un proyecto nuevo (modo 1) y a la mitad necesitas decidir DB (modo 3).

Claude lo maneja: termina el modo 1 con una nota "DB pendiente de decisión", luego ejecuta modo 3 puntual, vuelve al 1.

**Regla:** un modo a la vez en cada momento. No 3 mezclados.

---

## Filosofía (lo que hace este sistema distinto)

### 1. No valida por defecto
Cuando llegas con una idea, lo primero NO es "qué buena idea, vamos a hacerlo". Lo primero es "¿quién paga? ¿qué pasa si no lo construyes? ¿por qué ahora?". Si no resuelves esto, no se procede.

### 2. Honestidad brutal sobre suavidad falsa
Si tu proyecto está mal, te lo dice. Si quieres lanzar algo medio listo, te dice no-go. Decirte "casi" cuesta meses cuando lances algo que queme usuarios.

### 3. Calidad > cantidad
No es para entregar más proyectos. Es para entregar mejor cada proyecto. Si tienes 5 proyectos a medias, este sistema te va a forzar a matar 3 y terminar 2 bien.

### 4. Anti efecto Chavo
Si llegas con 5 ideas a la vez, te corta a 1. Si propones complejidad innecesaria, te la quita. Si quieres aprender 3 techs nuevas mientras construyes algo serio, te dice que escojas: aprender O entregar.

### 5. Production no es "funciona en mi máquina"
Production es "funciona bajo presión, a escala, en condiciones que no anticipaste, y cuando falle te enteras y arreglas". Cada playbook tiene esto en cuenta.

---

## Mantenimiento

Esto es vivo. Cada vez que un proyecto te enseñe algo:
- Patrón nuevo que aplicaste → lo agregas a `07_patterns_library.md`
- Pregunta que faltó en arranque → la agregas a `01_arrancar.md`
- Smell de refactor que descubriste → a `05_refactor.md`
- Receta de optimización que sirvió → a `06_optimizar.md`

Evoluciona con tu experiencia real. No con tendencias de Twitter.

---

## Estructura de archivos

```
tech-advisor/
├── SKILL.md                          ← Instalable como Claude Skill
├── README.md                         ← Este archivo
└── playbooks/
    ├── 01_arrancar.md                ← "Quiero hacer X"
    ├── 02_health_check.md            ← "¿Cómo voy?"
    ├── 03_consulta_rapida.md         ← Pregunta puntual
    ├── 04_get_ready_for.md           ← Transición de fase
    ├── 05_refactor.md                ← Limpiar código
    ├── 06_optimizar.md               ← Lento/caro/no escala
    └── 07_patterns_library.md        ← Referencia técnica
```

---

## Próximos pasos para vos

1. **Instala el skill** — sube la carpeta a Claude
2. **Pruébalo en algo real esta semana** — no en un proyecto hipotético
3. **Recomendación honesta:** usa el **modo 06 (optimizar)** con Adly. Tienes target claro (system prompt 2700→1200), pruebas el sistema y atacas deuda crítica al mismo tiempo. Dos pájaros.
4. **En 2 semanas, evalúa:** ¿lo usaste 3+ veces? Sirve. ¿No lo abriste? Era decoración.

---

## Una última cosa

Este sistema **no te va a hacer mejor developer por sí solo**.

Te va a obligar a tomar decisiones conscientes. Pero las decisiones las tomas tú. Si decides ignorar el no-go y lanzar igual, lo respetará. Si decides agregar features con deuda crítica pendiente, lo respetará. Si decides matar un proyecto que tenía valor, lo respetará.

La herramienta da el diagnóstico y la recomendación. La disciplina de seguirla es tuya.

Suerte, parcero. Ahora cierra esto y abre Adly.
