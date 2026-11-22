# Contrat d'interface DEV ↔ DATA

- **Projet :** SAÉ 3.01 « Climat & Cultures » — Équipe 06
- **Version :** v1.1
- **Date :** 22/11/2026
- **Statut :** Validé ensemble (DEV + DATA) — Jalon 2

Ce document définit **ce que DEV et DATA s'échangent** et **comment** : les colonnes, la fonction à appeler, les règles de calcul, les erreurs, la structure de `Fact_Indicateur`, l'identité de l'utilisateur (RGPD), et les jeux de test validés. Si une règle change, on modifie **ce fichier d'abord**, puis le code.

### Historique des versions
| Version | Date | Auteurs | Modifications principales |
|---|---|---|---|
| v1.0 | 12/11/2026 | Équipe 06 | Version initiale du contrat d'interface (J2) |
| v1.1 | 22/11/2026 | Équipe 06 (DATA + DEV) | Uniformisation `code_insee`, alignement structure `Fact_Indicateur` (moyennes par horizon), ajout des cas limites (année sans gel, canicule, multi-années), validation des décisions |

---

## Le principe : qui fait quoi, dans quel ordre

```
Utilisateur choisit : commune (code_insee) + culture + horizon
        │
        ▼
 DEV : client API ──► demande la météo à Open-Meteo
        │
        ▼
 Série climatique (tableau JSON, format de la partie A)
        │
        ▼
 DATA : fonction calculer_indicateur(...)          (partie C)
        │   lit dans la base : les seuils sourcés de la culture (Dim_Culture)
        │                      et la latitude de la commune (Dim_Commune)
        ▼
 Résultat (format de la partie B)  ou  Erreur (partie D)
        │
        ▼
 DEV : enregistre dans Fact_Indicateur (partie E) + affiche à l'utilisateur
```

---

## Ce que le contrat suppose dans la base

La base de données partagée est déployée sur **AlwaysData** (MySQL). Les valeurs de `Dim_Culture` sont strictement alignées avec le référentiel sourcé (instituts et dates de référence).

| Dimension | Colonnes utilisées | Remarque |
|---|---|---|
| `Dim_Culture` | `id_culture`, `t_base_c`, `plafond_gdd_c`, `gdd_maturite_cj`, `seuil_gel_c`, `seuil_stress_thermique_c`, `besoin_eau_mm` | `plafond_gdd_c` : `30` pour le maïs, `null` pour les autres cultures. `gdd_maturite_cj` peut être `null` (ex. olivier). |
| `Dim_Commune` | `code_insee`, `latitude` | `code_insee` en `VARCHAR(5)` (certains codes commencent par `0`). La latitude (en degrés décimaux, nord positif) sert au calcul de l'ET0. |
| `Dim_Modele` | `nom` | Les 7 modèles climatiques de l'API Open-Meteo. |

Identifiants des cultures : texte en minuscules, sans accent (`ble_tendre`, `mais_grain`, `tournesol`, `vigne`).

---

## Partie A — La série climatique (DEV → DATA)

Une ligne = un jour pour une commune et un modèle donnés.

| Colonne | Type | Exemple | Unité / règle | Nom dans l'API Open-Meteo |
|---|---|---|---|---|
| `code_insee` | texte | `"51454"` | Code INSEE. **Texte**, pas nombre : certains codes commencent par 0 (ex. `"01001"`). | (donné par DEV) |
| `date` | texte | `"2050-04-12"` | AAAA-MM-JJ | `time` |
| `t_min` | nombre décimal ou `null` | `-1.2` | °C | `temperature_2m_min` |
| `t_max` | nombre décimal ou `null` | `18.4` | °C | `temperature_2m_max` |
| `t_moy` | nombre décimal ou `null` | `8.6` | °C | `temperature_2m_mean` |
| `precip` | nombre décimal ou `null` | `3.5` | mm (jamais négatif) | `precipitation_sum` |

**Règles**
- **Valeur manquante :** on écrit `null`. **Jamais `0`**, car `0 °C` est une vraie température et `0 mm` est une absence de pluie réelle.
- Une série ne contient qu'**une seule commune** (`code_insee`), **un seul modèle climatique**, et **aucune date en double**. Sinon : erreur `SERIE_INVALIDE`.
- DEV demande à l'API les années de la période de l'horizon (voir partie C). DATA ne garde de toute façon que les lignes de cette période.
- La colonne `t_moy` est conservée (format standardisé) mais **les 4 indicateurs ne l'utilisent pas** : ils partent de `t_min`, `t_max` et `precip`.
- L'ET0 éventuellement fournie par l'API est **ignorée** : DATA la recalcule systématiquement avec la formule de Hargreaves-Samani, afin d'assurer l'homogénéité entre tous les modèles.

**Format d'échange : JSON** (décision 1). Exemple :

```json
[
  { "code_insee": "51454", "date": "2050-04-12", "t_min": -1.2, "t_max": 18.4, "t_moy": 8.6, "precip": 3.5 },
  { "code_insee": "51454", "date": "2050-04-13", "t_min":  0.5, "t_max": 20.1, "t_moy": 9.8, "precip": 0.0 },
  { "code_insee": "51454", "date": "2050-04-14", "t_min": null, "t_max": 19.0, "t_moy": null, "precip": 1.2 }
]
```

---

## Partie B — Le résultat (DATA → DEV)

Un résultat = **un indicateur agrégé (moyenne annuelle sur l'horizon)**, pour une commune, une culture, un horizon, un modèle et un utilisateur.

| Champ | Type | Exemple | Valeurs possibles / règle |
|---|---|---|---|
| `id_session` | texte | `"a3f9c2e17b4d4a0e9c1d5b7f2e8a6c30"` | recopié de la demande (partie E) |
| `id_utilisateur` | texte ou `null` | `null` | recopié de la demande ; `null` si le visiteur n'est pas connecté |
| `code_insee` | texte | `"51454"` | le même que dans la série |
| `id_culture` | texte | `"vigne"` | un identifiant de `Dim_Culture` |
| `horizon` | texte | `"2050"` | `"2030"`, `"2040"`, `"2050"` ou `"reference"` |
| `modele` | texte | `"MRI_AGCM3_2_S"` | un modèle de `Dim_Modele` |
| `periode` | texte | `"2041-2050"` | les années réellement visées (partie C) |
| `indicateur` | texte | `"jours_gel"` | `"jours_gel"`, `"gdd"`, `"stress_thermique"`, `"bilan_hydrique"`, `"viabilite"` |
| `valeur` | nombre décimal ou `null` | `2.0` | **moyenne par année** sur la période ; `null` pour `viabilite` |
| `unite` | texte ou `null` | `"jours"` | `"jours"`, `"°C·j"`, `"mm"` ; `null` pour `viabilite` |
| `verdict` | texte ou `null` | `"a_risque"` | `"viable"`, `"a_risque"`, `"non_viable"` ou `null` (partie C) |
| `nb_annees` | nombre entier | `1` | nombre d'années qui ont au moins un jour valide dans la fenêtre |
| `nb_jours_ignores` | nombre entier | `0` | jours de la fenêtre écartés à cause d'une valeur `null` |

Exemple :

```json
{
  "id_session": "a3f9c2e17b4d4a0e9c1d5b7f2e8a6c30",
  "id_utilisateur": null,
  "code_insee": "51454",
  "id_culture": "vigne",
  "horizon": "2050",
  "modele": "MRI_AGCM3_2_S",
  "periode": "2041-2050",
  "indicateur": "jours_gel",
  "valeur": 2.0,
  "unite": "jours",
  "verdict": "a_risque",
  "nb_annees": 1,
  "nb_jours_ignores": 0
}
```

---

## Partie C — Comment DEV appelle DATA, et comment DATA calcule

### L'appel

```python
calculer_indicateur(serie, id_culture, indicateur, horizon, modele, identite) -> dict
```

| Paramètre | Ce que c'est | Exemple |
|---|---|---|
| `serie` | la série climatique (partie A) | le tableau JSON / liste de dictionnaires |
| `id_culture` | la culture choisie | `"vigne"` |
| `indicateur` | l'indicateur voulu | `"jours_gel"` |
| `horizon` | l'horizon voulu | `"2050"` |
| `modele` | le modèle utilisé pour la série | `"MRI_AGCM3_2_S"` |
| `identite` | l'utilisateur (partie E) | `{ "id_session": "a3f9…", "id_utilisateur": null }` |

DEV **ne passe pas** les seuils de la culture ni la latitude : la fonction les lit directement en base dans `Dim_Culture` et `Dim_Commune`. Les identifiants de connexion AlwaysData sont stockés uniquement dans un fichier `.env` local **exclu de Git** (`.gitignore`).

### La période : que veut dire « horizon 2050 » ?

| `horizon` | `periode` (années prises en compte) |
|---|---|
| `"2030"` | 2021-2030 |
| `"2040"` | 2031-2040 |
| `"2050"` | 2041-2050 |
| `"reference"` | 1991-2020 (normale OMM de référence) |

Pour comparer un horizon futur au passé récent, DEV appelle la fonction **deux fois** : une fois avec l'horizon cible, une fois avec `"reference"`.

### La fenêtre

Pour la version MVP, **tous les indicateurs** comptent les jours du **1er avril au 31 octobre** (saison de croissance), pour toutes les cultures. Les jours hors de cette fenêtre sont filtrés sans être comptés dans `nb_jours_ignores`.

### Les règles de calcul

Pour chaque année de la période ayant au moins un jour valide dans la fenêtre, on calcule le total annuel sur la fenêtre. La `valeur` du résultat est la **moyenne arithmétique de ces totaux annuels** (`somme_totaux_annuels / nb_annees`).

**Décision explicite sur les comparaisons aux seuils :**
- **Gel :** inégalité **stricte** (`t_min < seuil_gel_c`). Une journée dont `t_min == seuil_gel_c` n'est **pas** comptée comme un jour de gel.
- **Stress thermique :** inégalité **stricte** (`t_max > seuil_stress_thermique_c`). Une journée dont `t_max == seuil_stress_thermique_c` n'est **pas** comptée comme un jour de stress.

| Indicateur | Contribution d'un jour | Jour ignoré si | Unité | Source de la règle |
|---|---|---|---|---|
| `jours_gel` | `1` si `t_min < seuil_gel_c` (strictement), sinon `0` | `t_min` est `null` | `jours` | amorçage DATA, décision d'équipe |
| `stress_thermique` | `1` si `t_max > seuil_stress_thermique_c` (strictement), sinon `0` | `t_max` est `null` | `jours` | amorçage DATA, décision d'équipe |
| `gdd` | `max( (t_min + min(t_max, plafond)) / 2 − t_base_c , 0 )` ; si `plafond_gdd_c` est `null`, on prend `t_max` | `t_min` ou `t_max` est `null`, ou `t_max < t_min` | `°C·j` | formule DRIAS / projet ORACLE |
| `bilan_hydrique` | `precip − ET0` | `t_min`, `t_max` ou `precip` est `null`, ou `t_max < t_min` | `mm` | amorçage DATA ; ET0 : Hargreaves-Samani (FAO-56) |

**ET0 par Hargreaves-Samani :**
`ET0 = 0,0023 × (Tmoy + 17,8) × √(t_max − t_min) × Ra`, avec `Tmoy = (t_min + t_max) / 2` et `Ra` le rayonnement extraterrestre en mm/jour (calculé à partir de la latitude de la commune et du jour julien selon la formule FAO-56). Si `ET0 < 0`, on la ramène à `0`.

### Le verdict

Chaque indicateur reçoit un verdict calculé à partir de sa `valeur` (moyenne annuelle). Ces seuils constituent la règle MVP validée par le pôle DATA :

| Indicateur | `viable` | `a_risque` | `non_viable` |
|---|---|---|---|
| `jours_gel` | `valeur == 0` | `0 < valeur <= 3` | `valeur > 3` |
| `stress_thermique` | `valeur <= 5` | `5 < valeur <= 15` | `valeur > 15` |
| `gdd` | `valeur >= gdd_maturite_cj` | `0.90 * gdd_maturite_cj <= valeur < gdd_maturite_cj` | `valeur < 0.90 * gdd_maturite_cj` |
| `bilan_hydrique` | `valeur >= 0` | `-0.50 * besoin_eau_mm <= valeur < 0` | `valeur < -0.50 * besoin_eau_mm` |

- Si `gdd_maturite_cj` est `null` (ex. olivier), le verdict du `gdd` est `null`.
- `viabilite` : la fonction évalue les 4 indicateurs et retourne **le verdict le plus défavorable** (`non_viable` > `a_risque` > `viable`). Pour `viabilite`, `valeur` et `unite` valent `null`, et `nb_jours_ignores` est le maximum des quatre.

---

## Partie D — Les erreurs

Si le calcul ne peut pas aboutir, la fonction retourne un objet d'erreur normalisé :

```json
{ "erreur": "CULTURE_INCONNUE", "message": "La culture 'riz' n'existe pas dans Dim_Culture." }
```

| Code | Condition de déclenchement | Action côté DEV |
|---|---|---|
| `IDENTITE_MANQUANTE` | `id_session` absent ou vide | corrige son appel |
| `INDICATEUR_INCONNU` | `indicateur` absent de la liste autorisée | corrige son appel |
| `HORIZON_INCONNU` | `horizon` différent de `"2030"`, `"2040"`, `"2050"`, `"reference"` | corrige son appel |
| `CULTURE_INCONNUE` | `id_culture` absent de `Dim_Culture` | affiche un message d'erreur |
| `MODELE_INCONNU` | `modele` absent de `Dim_Modele` | affiche un message d'erreur |
| `COMMUNE_INCONNUE` | `code_insee` absent de `Dim_Commune` | affiche un message d'erreur |
| `SERIE_VIDE` | aucune ligne fournie, ou aucune ligne dans la période et la fenêtre | affiche « données indisponibles » |
| `SERIE_INVALIDE` | plusieurs communes, date en double, ou format de date invalide | corrige le prétraitement API |
| `DONNEES_INSUFFISANTES` | plus de 50 % des jours de la fenêtre sont inutilisables (`null`) | affiche un avertissement à l'utilisateur |

Si **l'API Open-Meteo** échoue (timeout, erreur HTTP), DEV n'appelle pas `calculer_indicateur` et affiche « données indisponibles ».

---

## Partie E — Structure de `Fact_Indicateur`, identité RGPD et persistance

### Granularité de `Fact_Indicateur`
Conformément au schéma en étoile, **une ligne de `Fact_Indicateur` stocke le résultat agrégé (moyenne annuelle sur l'horizon) d'un indicateur**, et **non** des valeurs ou booléens journaliers.

| Colonne | Type SQL | Clé / Contrainte | Description |
|---|---|---|---|
| `id_session` | `VARCHAR(32)` | `PK` | Identifiant de session anonyme (cookie, toujours présent) |
| `id_utilisateur` | `VARCHAR(64)` | `NULL` | Identifiant utilisateur si connecté, sinon `NULL` |
| `code_insee` | `VARCHAR(5)` | `PK, FK -> Dim_Commune` | Code INSEE de la commune |
| `id_culture` | `VARCHAR(50)` | `PK, FK -> Dim_Culture` | Identifiant de la culture |
| `horizon` | `VARCHAR(20)` | `PK` | `"2030"`, `"2040"`, `"2050"` ou `"reference"` |
| `modele` | `VARCHAR(50)` | `PK, FK -> Dim_Modele` | Nom du modèle climatique |
| `indicateur` | `VARCHAR(30)` | `PK` | Nom de l'indicateur calculé |
| `valeur` | `DECIMAL(10,2)` | `NULL` | Moyenne annuelle calculée (`NULL` pour `viabilite`) |
| `unite` | `VARCHAR(15)` | `NULL` | Unité de mesure |
| `verdict` | `VARCHAR(20)` | `NULL` | `"viable"`, `"a_risque"`, `"non_viable"` ou `NULL` |
| `nb_annees` | `INT` | `NOT NULL` | Nombre d'années prises en compte |
| `nb_jours_ignores` | `INT` | `NOT NULL` | Nombre de jours écartés (`null`) |
| `date_calcul` | `DATETIME` | `NOT NULL` | Horodatage du calcul (traçabilité / purge RGPD) |

### Enregistrement (Upsert)
DEV enregistre chaque résultat retourné par DATA via la requête fournie par DATA (aucun doublon sur la clé primaire composite) :

```sql
INSERT INTO Fact_Indicateur (
    id_session, id_utilisateur, code_insee, id_culture, horizon, modele,
    indicateur, valeur, unite, verdict, nb_annees, nb_jours_ignores, date_calcul
) VALUES (
    :id_session, :id_utilisateur, :code_insee, :id_culture, :horizon, :modele,
    :indicateur, :valeur, :unite, :verdict, :nb_annees, :nb_jours_ignores, NOW()
)
ON DUPLICATE KEY UPDATE
    id_utilisateur = VALUES(id_utilisateur),
    valeur = VALUES(valeur),
    unite = VALUES(unite),
    verdict = VALUES(verdict),
    nb_annees = VALUES(nb_annees),
    nb_jours_ignores = VALUES(nb_jours_ignores),
    date_calcul = NOW();
```

### Effacement (Conformité RGPD)
```sql
DELETE FROM Fact_Indicateur WHERE id_session = :id_session;          -- bouton « réinitialiser mes données »
DELETE FROM Fact_Indicateur WHERE id_utilisateur = :id_utilisateur;  -- suppression du compte utilisateur
```

---

## Partie F — Jeu de tests de référence (résultats attendus calculés à la main)

Tous les tests ci-dessous utilisent la commune `51454` (Reims, latitude `49.2583`), le modèle `MRI_AGCM3_2_S`, l'horizon `"2050"` (sauf mention contraire) et un `id_session` valide non vide. Les seuils utilisés sont ceux de `Dim_Culture`.

### Test 1 — Jours de gel et journée exactement au seuil (`vigne`, `seuil_gel_c = -2.0`)
Règle appliquée : `t_min < -2.0` (strictement).

| `date` | `t_min` (°C) | Compté comme gel ? | Justification |
|---|---|---|---|
| `2050-04-10` | `-5.0` | Oui (`1`) | `-5.0 < -2.0` |
| `2050-04-11` | `-1.0` | Non (`0`) | `-1.0 >= -2.0` |
| `2050-04-12` | `-3.2` | Oui (`1`) | `-3.2 < -2.0` |
| `2050-04-13` | `0.4` | Non (`0`) | `0.4 >= -2.0` |
| `2050-04-14` | `-2.0` | Non (`0`) | `-2.0 == -2.0` (cas limite au seuil exact : strictement `<`, donc exclu) |

**Résultat attendu :** `valeur = 2.0` (`-5.0` et `-3.2`), `nb_annees = 1`, `nb_jours_ignores = 0`, `verdict = "a_risque"`.

---

### Tableau complet des cas nominaux et cas limites

| # | Cas testé | Paramètres & Entrée | Résultat attendu (calculé à la main) |
|---|---|---|---|
| **2** | **GDD avec plafond** (`mais_grain`, `t_base_c = 6`, `plafond_gdd_c = 30`) | `2050-07-01` : `t_min = 14`, `t_max = 38` ; `2050-07-02` : `t_min = 2`, `t_max = 8` | `valeur = 16.0` °C·j (J1 : `(14+30)/2 - 6 = 16` ; J2 : `(2+8)/2 - 6 = -1` ramené à `0`), `nb_annees = 1`, `nb_jours_ignores = 0` |
| **3** | **Stress thermique & seuil exact** (`mais_grain`, `seuil_stress_thermique_c = 35.0`) | `t_max` : `38.0`, `35.0`, `36.1` | `valeur = 2.0` jours (`35.0` pile est exclu car `>` strict), `verdict = "viable"` |
| **4** | **Valeur manquante (`null`)** (`vigne`, `seuil_gel_c = -2.0`) | 4 jours en avril : `-5.0`, `null`, `-3.2`, `0.4` | `nb_jours_ignores = 1`, `valeur = 2.0`, `verdict = "a_risque"` |
| **5** | **Culture inconnue** | `id_culture = "riz"` | Erreur `CULTURE_INCONNUE` |
| **6** | **Trop de valeurs manquantes (> 50 %)** | 3 jours dans la fenêtre dont 2 avec `t_min = null` | Erreur `DONNEES_INSUFFISANTES` |
| **7** | **Bilan hydrique d'un jour** (`vigne`) | `2050-06-21` : `t_min = 12`, `t_max = 25`, `precip = 0` | `valeur = -5.13` mm (ET0 ≈ `5.13` mm/jour, tolérance `± 0.05`) |
| **8** | **Série hors période** | 1 seule ligne datée du `2020-04-10` avec `horizon = "2050"` | Erreur `SERIE_VIDE` |
| **9** | **Identité manquante** | `id_session = ""` | Erreur `IDENTITE_MANQUANTE` |
| **10** | **Viabilité (pire verdict)** (`vigne`) | `2050-04-10` (`t_min = -5`, `t_max = 12`, `precip = 2`) ; `2050-07-10` (`t_min = 15`, `t_max = 37`, `precip = 0`) | `jours_gel` (`a_risque`), `gdd` (`non_viable`), `stress_thermique` (`viable`), `bilan_hydrique` (`a_risque`) → `viabilite` : `verdict = "non_viable"`, `valeur = null` |
| **11** | **Cas limite : Année sans aucun gel** (`vigne`, `seuil_gel_c = -2.0`) | `2050-04-10` : `t_min = 2.5` ; `2050-04-11` : `t_min = 4.0` ; `2050-05-01` : `t_min = 8.2` | `valeur = 0.0` jour, `nb_annees = 1`, `nb_jours_ignores = 0`, `verdict = "viable"` |
| **12** | **Cas limite : Canicule prolongée** (`mais_grain`, `seuil_stress_thermique_c = 35.0`) | 6 jours consécutifs en juillet 2050 avec `t_max = 38.0` °C | `valeur = 6.0` jours, `nb_annees = 1`, `nb_jours_ignores = 0`, `verdict = "a_risque"` (`5 < 6 <= 15`) |
| **13** | **Cas limite : Série multi-annuelle (moyenne sur 2 ans)** (`vigne`, `seuil_gel_c = -2.0`) | Année 2049 : 2 jours à `-4.0` °C (total 2049 = `2`) ; Année 2050 : 4 jours à `-3.5` °C (total 2050 = `4`) | `valeur = 3.0` jours (`(2 + 4) / 2`), `nb_annees = 2`, `nb_jours_ignores = 0`, `verdict = "a_risque"` |

---

## Les décisions actées ensemble (DEV + DATA)

| # | Question | Décision retenue | Justification | Validé |
|---|---|---|---|---|
| 1 | Format d'échange : JSON ou CSV ? | **JSON** | L'API Open-Meteo répond en JSON ; évite une double conversion. | ☑ |
| 2 | Qui écrit dans `Fact_Indicateur` ? | **DATA calcule, DEV enregistre** | DATA fournit la fonction de calcul et la requête SQL ; DEV orchestre l'insertion. | ☑ |
| 3 | Que veut dire « horizon » ? | **10 années finissant à l'horizon**, `"reference"` = `1991-2020` | L'API s'arrête en 2050 ; `1991-2020` correspond à la normale OMM. | ☑ |
| 4 | La fonction lit-elle seuils et latitude elle-même ? | **Oui**, dans `Dim_Culture` et `Dim_Commune` via `.env` | Garantit la source unique de vérité en base AlwaysData. | ☑ |
| 5 | Quelle fenêtre pour le MVP ? | **1er avril → 31 octobre pour toutes les cultures** | Couvre la saison de croissance et les gelées tardives/précoces. | ☑ |
| 6 | Quelles règles de verdict ? | **Seuils de la partie C** | Règle déterministe validée par DATA pour le MVP. | ☑ |
| 7 | Codes d'erreur et règle des 50 % ? | **Liste de la partie D** | Permet une gestion propre des séries incomplètes ou invalides. | ☑ |
| 8 | Ajouter `plafond_gdd_c` (`Dim_Culture`) et `latitude` (`Dim_Commune`) ? | **Oui** | Indispensables pour le calcul du GDD plafonné (maïs) et de l'ET0 (Hargreaves). | ☑ |

---

## Limites connues du MVP

- **Le blé tendre d'hiver** a un cycle à cheval sur deux années civiles (semis en octobre, récolte en juillet) : la fenêtre `1er avril → 31 octobre` ne couvre qu'une partie de son cycle. Le MVP s'appuie en priorité sur la **vigne** et le **maïs grain**.
- **`jours_gel`** mesure un nombre cumulé de jours sous le seuil sur la fenêtre, sans pondération par stade phénologique (débourrement, floraison), qui pourra être affinée en Sprint 2.
