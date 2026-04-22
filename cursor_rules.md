# Gestion des relations (IMPORTANT)

- Aucune utilisation de ForeignKey  
- Utiliser uniquement des champs ID  
- Gestion des relations côté logique applicative  
- Type des IDs strictement cohérent entre les modèles  

---

# Pagination, filtrage et performance des GET (OBLIGATOIRE)

## Pagination

- Obligatoire pour tout GET liste  
- Interdiction de retourner toute la base  

**Paramètres :**
- page  
- page_size (défaut = 25)  

**Tri :**
- du plus récent au plus ancien  

---

## Format de réponse

Chaque réponse doit contenir :  
- results  
- count  
- page  
- page_size  
- statistiques si nécessaires  

---

## Filtrage

- Filtres dynamiques via URL  
- Filtres obligatoires :  
  - date_from / date_to  
  - champs métiers  
  - champs ID (relations)  

---

## Relations (sans ForeignKey)

- Jointures manuelles via ORM :  
  - INNER JOIN  
  - LEFT JOIN  
- Optimisation obligatoire  

---

# Interdictions strictes

- Ne jamais utiliser d’emojis  (utilise plutot fontawesome)
