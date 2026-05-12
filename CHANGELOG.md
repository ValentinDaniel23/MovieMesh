# Evolutia proiectului MovieMesh

Am creat acest fisier pentru a urmari evolutia proiectului MovieMesh si pentru a nota, pe scurt, ce s-a schimbat in fiecare etapa importanta a repository-ului.

## Istoric pe commit-uri

### 2026-04-26 - `45a97be` - Movies-data-service

### Added

- A fost pastrata si organizata partea de date in noua structura, pentru securitate si scalarea mai buna a serviciilor.
- A fost clarificata delimitarea dintre accesul la date si logica de business, astfel incat fiecare serviciu sa aiba o responsabilitate mai bine definita.

### Changed

- Logica din `movies-service` a fost impartita si mutata in `movies-data-service`.
- `movies-service` a ramas mai curat si mai usor de intretinut, iar partea specifica de modele si date a fost extrasa intr-un serviciu separat.

### Removed

- Fisierul `models.py` a fost scos din `movies-service`.

### 2026-03-28 - `91170686` - ETAPA1.md

### Added

- A fost creat `ETAPA1.md` cu scopul proiectului, echipa, arhitectura si directia generala a platformei.

### 2026-01-15 - `18727855` - done

### Added

- A fost construita baza aplicatiei MovieMesh: stack-ul, serviciile principale, integrarea cu Keycloak, mesageria si interfata web.

### 2025-11-23 - `9cde7504` - Initial commit

### Added

- A fost creat repository-ul initial si a inceput proiectul MovieMesh.

## Contributii ale echipei

### Valentin Chipuc

- A pornit proiectul de la o baza existenta, cu scheletul si ideea deja conturate inainte de cerinta finala a proiectului.
- A realizat commit-ul initial, pornind repository-ul si structura de baza a proiectului.
- A adaugat documentatia de etapa in `ETAPA1.md`, in care a descris scopul aplicatiei si arhitectura generala.

### Florin Dinu

- A lucrat la integrarea `movies-data-service`, separand zona de acces la date de restul logicii aplicatiei.
- A contribuit la integrarea cu PostgreSQL si Redis, pentru persistenta si cache.
- A sustinut evolutia arhitecturii catre o structura mai clara, bazata pe servicii specializate.
- Ultimul commit, realizat de Florin, a mutat logica din `movies-service` in `movies-data-service` si a relocat fisierul `models.py`.