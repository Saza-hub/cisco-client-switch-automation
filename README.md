# Cisco Client Switch Automation

Workflows pour préparer les configurations de switches **Cisco IOS / IOS-XE** selon les besoins clients.

## Capacités

- Profils clients en YAML : VLAN, interfaces access/trunk, VLAN de management et adresse IP.
- Validation des profils et génération de configurations Cisco.
- Tests automatiques avec GitHub Actions.
- Déploiement SSH **optionnel** avec Netmiko, uniquement après approbation explicite (`--approve`).
- Sauvegarde locale du `running-config` avant application des commandes.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Sous Windows, activer l'environnement avec `.venv\Scripts\activate`.

## Valider et générer

```bash
python -m src.switchctl validate --profile clients/client-demo.yaml
python -m src.switchctl generate --profile clients/client-demo.yaml
```

La configuration est produite dans `output/` (non versionné). Adapter `clients/client-demo.yaml` pour un client réel et faire relire le résultat par un administrateur réseau.

## Déployer uniquement sur un équipement autorisé

Copier `inventory/devices.example.yaml` vers `inventory/devices.yaml` et définir une adresse IP réelle. Conserver cet inventaire hors de Git, tout comme les identifiants.

```bash
export CISCO_USERNAME='network-admin'
export CISCO_PASSWORD='...'
export CISCO_ENABLE_SECRET='...'
python -m src.switchctl deploy --profile clients/client-demo.yaml --inventory inventory/devices.yaml --device switch-demo --approve
```

**Important :** cette commande modifie le `running-config` de l'équipement. Aucun déploiement automatique depuis GitHub Actions, aucun rollback automatique, et aucune sauvegarde automatique dans le `startup-config`. Tester d'abord en laboratoire, valider les interfaces et disposer d'un accès de secours. La configuration générée est une base partielle, pas un remplacement intégral de la configuration existante. Sur un réseau de production, privilégier une fenêtre de changement approuvée.

## Organisation

- `src/switchctl.py` : validation, génération et déploiement SSH.
- `clients/client-demo.yaml` : exemple de besoin client.
- `inventory/devices.example.yaml` : exemple d'inventaire.
- `tests/test_switchctl.py` : tests unitaires.
- `.github/workflows/validate.yml` : pipeline de validation.

Aucun secret ni configuration réelle client ne doit être publié dans ce dépôt.
