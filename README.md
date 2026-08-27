# Site de la Respectable Loge Mixte Videlina

## Lancer le site

```powershell
python -m pip install -r requirements.txt
python app.py
```

Ouvrez ensuite `http://127.0.0.1:5000` dans votre navigateur.

Le formulaire de contact est une démonstration locale : il valide l’envoi et affiche une confirmation. Avant publication, reliez-le à une adresse e-mail ou à un service de formulaire sécurisé.

## Espace membre

Ouvrez `http://127.0.0.1:5000/setup` au premier démarrage pour créer le compte administrateur. L’administrateur gère les membres, les réunions et les références documentaires. Avant une mise en ligne, définissez une clé longue et aléatoire dans la variable d’environnement `VIDELINA_SECRET_KEY`.
