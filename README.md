# Cisco Client Switch Automation

Workflows réutilisables pour **switches Cisco IOS / IOS-XE** : besoin client en YAML → validation → génération de configuration → revue humaine → sauvegarde → déploiement SSH optionnel. Ce dépôt ne contient **aucun accès réel** ni mot de passe.

## Workflows

1. **Recueil du besoin** : dupliquer `clients/client-demo.yaml` puis renseigner hostname, VLAN, IP management, ports access/trunk et descriptions.
2. **Validation automatique** : `python -m src.switchctl validate --profile clients/client-demo.yaml`. Les pull requests et pushes passent des tests GitHub Actions.
3. **Génération** : `python -m src.switchctl generate --profile clients/client-demo.yaml` → fichier local `output/SW-CLIENT-DEMO-01.cfg` (non versionné).
4. **Revue / changement** : faire contrôler les VLAN, trunks, uplinks, IP, modèles Cisco, ports physiques et fenêtre de maintenance. La configuration générée est une *base*, pas un remplacement complet.
5. **Déploiement optionnel** : sauvegarder le running-config, envoyer les commandes via SSH après autorisation explicite ; pas de `write memory` automatique. Opérateur sur console ou chemin de secours recommandé.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows : .venv\\Scripts\\activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.switchctl generate --profile clients/client-demo.yaml
```

## Déployer (réseau autorisé uniquement)

Créer `inventory/devices.yaml` à partir de l'exemple, avec l'adresse IP réelle. Ne pas committer ce fichier.

```bash
export CISCO_USERNAME='network-admin'
export CISCO_PASSWORD='...'  # préférable : injection depuis un coffre à secrets
export CISCO_ENABLE_SECRET='...' # si nécessaire
python -m src.switchctl deploy --profile clients/client-demo.yaml \
  --inventory inventory/devices.yaml --device switch-demo --approve
```

⚠️ **Attention** : `deploy` modifie la configuration active, et peut interrompre l'accès réseau. Le script tente de sauvegarder l'état préalable dans `output/` avant envoi, mais il n'effectue ni rollback automatique ni sauvegarde du startup-config. Employer seulement après validation sur labo et contrôle des interfaces du modèle précis. Les commandes `service password-encryption` ne remplacent pas des secrets robustes ni AAA. Le déploiement n'est pas exécuté par GitHub Actions (pas d'accès automatique au réseau client).

## Limitations / adaptations

Couvre le socle L2 IOS/IOS-XE (VLAN, ports access/trunk, SVI management, passerelle). Adapter selon le modèle, la version IOS, l'existant et les politiques : AAA/RADIUS, SSH, NTP, SNMPv3, DHCP snooping, port security, EtherChannel, PoE, STP, sauvegardes et conformité. Le générateur ne compare pas encore la configuration existante, et n'essaie pas de supprimer les objets inconnus.

**Sécurité** : ne jamais placer des mots de passe ou vraies configurations clients dans un dépôt public. Utiliser un dépôt privé pour des besoins clients réels.
