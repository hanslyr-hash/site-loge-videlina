import os
import sqlite3
import uuid

from datetime import date
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from werkzeug.utils import secure_filename


# =========================================================
# CONFIGURATION
# =========================================================

ROOT = Path(__file__).resolve().parent

app = Flask(__name__)

app.config.update(
    SECRET_KEY=os.getenv(
        "VIDELINA_SECRET_KEY",
        "change-this-secret-before-production"
    ),

    DATABASE=ROOT / "data" / "videlina.db",

    # Dossier privé des ouvrages
    LIBRARY_FOLDER=ROOT / "private_library",

    # Taille maximale d'un fichier : 20 Mo
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
)


# Formats autorisés
ALLOWED_LIBRARY_EXTENSIONS = {
    "pdf",
    "epub",
}


# =========================================================
# BASE DE DONNÉES
# =========================================================

def db():

    if "db" not in g:

        app.config["DATABASE"].parent.mkdir(
            exist_ok=True
        )

        g.db = sqlite3.connect(
            app.config["DATABASE"]
        )

        g.db.row_factory = sqlite3.Row

    return g.db


@app.teardown_appcontext
def close_db(_error=None):

    database = g.pop("db", None)

    if database is not None:
        database.close()


# =========================================================
# INITIALISATION DES TABLES
# =========================================================

@app.before_request
def initialise():

    db().executescript("""

        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Membre',
            status TEXT NOT NULL DEFAULT 'Actif'
        );


        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            meeting_date TEXT NOT NULL,
            location TEXT NOT NULL,
            notes TEXT
        );


        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            reference TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS library_items (
            id INTEGER PRIMARY KEY,

            title TEXT NOT NULL,

            author TEXT,

            category TEXT NOT NULL,

            description TEXT,

            stored_name TEXT NOT NULL,

            original_name TEXT NOT NULL,

            file_extension TEXT NOT NULL,

            added_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );

    """)

    db().commit()

    # Création du dossier privé
    app.config["LIBRARY_FOLDER"].mkdir(
        parents=True,
        exist_ok=True
    )


# =========================================================
# AUTHENTIFICATION
# =========================================================

def login_required(view):

    @wraps(view)
    def wrapper(*args, **kwargs):

        if "member_id" not in session:

            flash(
                "Veuillez vous connecter.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapper


def admin_required(view):

    @wraps(view)
    def wrapper(*args, **kwargs):

        if session.get("member_role") != "Administrateur":

            flash(
                "Action réservée aux administrateurs.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return view(*args, **kwargs)

    return wrapper


# =========================================================
# ACCUEIL
# =========================================================

@app.get("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# CONTACT
# =========================================================

@app.post("/contact")
def contact():

    values = [
        request.form.get(
            key,
            ""
        ).strip()

        for key in (
            "name",
            "email",
            "subject",
            "message"
        )
    ]

    return render_template(
        "index.html",
        sent=all(values),
        form=request.form
    )


# =========================================================
# PREMIÈRE INSTALLATION
# =========================================================

@app.route(
    "/setup",
    methods=["GET", "POST"]
)
def setup():

    if db().execute(
        "SELECT COUNT(*) FROM members"
    ).fetchone()[0]:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        if (
            not name
            or not email
            or len(password) < 10
        ):

            flash(
                "Indiquez un nom, un e-mail et un mot de passe d’au moins 10 caractères.",
                "error"
            )

        else:

            db().execute(
                """
                INSERT INTO members
                (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                    "Administrateur"
                )
            )

            db().commit()

            flash(
                "Administrateur créé. Vous pouvez vous connecter.",
                "success"
            )

            return redirect(
                url_for("login")
            )


    return render_template(
        "setup.html"
    )


# =========================================================
# CONNEXION
# =========================================================

@app.route(
    "/connexion",
    methods=["GET", "POST"]
)
def login():

    if not db().execute(
        "SELECT COUNT(*) FROM members"
    ).fetchone()[0]:

        return redirect(
            url_for("setup")
        )


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        member = db().execute(
            """
            SELECT *
            FROM members
            WHERE email=?
            """,
            (email,)
        ).fetchone()


        if (
            member
            and member["status"] == "Actif"
            and check_password_hash(
                member["password_hash"],
                password
            )
        ):

            session.clear()

            session.update(
                member_id=member["id"],
                member_name=member["name"],
                member_role=member["role"]
            )

            return redirect(
                url_for("dashboard")
            )


        flash(
            "Adresse e-mail, mot de passe incorrect ou compte inactif.",
            "error"
        )


    return render_template(
        "login.html"
    )


# =========================================================
# DÉCONNEXION
# =========================================================

@app.get("/deconnexion")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# TABLEAU DE BORD
# =========================================================

@app.get("/membres")
@login_required
def dashboard():

    database = db()

    counts = {

        "members":
            database.execute(
                """
                SELECT COUNT(*)
                FROM members
                WHERE status='Actif'
                """
            ).fetchone()[0],

        "meetings":
            database.execute(
                """
                SELECT COUNT(*)
                FROM meetings
                WHERE meeting_date>=?
                """,
                (date.today().isoformat(),)
            ).fetchone()[0],

        "documents":
            database.execute(
                """
                SELECT COUNT(*)
                FROM documents
                """
            ).fetchone()[0],

        "library":
            database.execute(
                """
                SELECT COUNT(*)
                FROM library_items
                """
            ).fetchone()[0],
    }


    return render_template(
        "dashboard.html",

        counts=counts,

        meetings=database.execute(
            """
            SELECT *
            FROM meetings
            ORDER BY meeting_date
            LIMIT 6
            """
        ).fetchall(),

        documents=database.execute(
            """
            SELECT *
            FROM documents
            LIMIT 6
            """
        ).fetchall()
    )


# =========================================================
# GESTION DES MEMBRES
# =========================================================

@app.route(
    "/membres/gestion",
    methods=["GET", "POST"]
)
@login_required
@admin_required
def manage_members():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        role = request.form.get(
            "role",
            "Membre"
        )

        password = request.form.get(
            "password",
            ""
        )


        try:

            if (
                not name
                or not email
                or len(password) < 10
            ):
                raise ValueError


            db().execute(
                """
                INSERT INTO members
                (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                    role
                )
            )

            db().commit()

            flash(
                "Membre ajouté.",
                "success"
            )


        except ValueError:

            flash(
                "Indiquez le nom, l’e-mail et un mot de passe provisoire d’au moins 10 caractères.",
                "error"
            )


        except sqlite3.IntegrityError:

            flash(
                "Cette adresse e-mail est déjà utilisée.",
                "error"
            )


    return render_template(
        "members.html",

        members=db().execute(
            """
            SELECT
                id,
                name,
                email,
                role,
                status
            FROM members
            ORDER BY name
            """
        ).fetchall()
    )


# =========================================================
# ACTIVATION / DÉSACTIVATION D'UN MEMBRE
# =========================================================

@app.post(
    "/membres/<int:member_id>/statut"
)
@login_required
@admin_required
def toggle_member_status(member_id):

    member = db().execute(
        """
        SELECT status
        FROM members
        WHERE id=?
        """,
        (member_id,)
    ).fetchone()


    if (
        member
        and member_id != session["member_id"]
    ):

        new_status = (
            "Inactif"
            if member["status"] == "Actif"
            else "Actif"
        )

        db().execute(
            """
            UPDATE members
            SET status=?
            WHERE id=?
            """,
            (
                new_status,
                member_id
            )
        )

        db().commit()


    return redirect(
        url_for("manage_members")
    )


# =========================================================
# RÉUNIONS
# =========================================================

@app.route(
    "/reunions",
    methods=["GET", "POST"]
)
@login_required
def manage_meetings():

    if (
        request.method == "POST"
        and session.get("member_role")
        == "Administrateur"
    ):

        data = [
            request.form.get(
                key,
                ""
            ).strip()

            for key in (
                "title",
                "meeting_date",
                "location",
                "notes"
            )
        ]


        if all(data[:3]):

            db().execute(
                """
                INSERT INTO meetings
                (title, meeting_date, location, notes)
                VALUES (?, ?, ?, ?)
                """,
                data
            )

            db().commit()

            flash(
                "Réunion enregistrée.",
                "success"
            )


    return render_template(
        "meetings.html",

        meetings=db().execute(
            """
            SELECT *
            FROM meetings
            ORDER BY meeting_date DESC
            """
        ).fetchall()
    )


# =========================================================
# DOCUMENTS
# =========================================================

@app.route(
    "/documents",
    methods=["GET", "POST"]
)
@login_required
def manage_documents():

    if (
        request.method == "POST"
        and session.get("member_role")
        == "Administrateur"
    ):

        data = [
            request.form.get(
                key,
                ""
            ).strip()

            for key in (
                "title",
                "category",
                "reference"
            )
        ]


        if all(data):

            db().execute(
                """
                INSERT INTO documents
                (title, category, reference)
                VALUES (?, ?, ?)
                """,
                data
            )

            db().commit()

            flash(
                "Référence ajoutée.",
                "success"
            )


    return render_template(
        "documents.html",

        documents=db().execute(
            """
            SELECT *
            FROM documents
            ORDER BY title
            """
        ).fetchall()
    )


# =========================================================
# BIBLIOTHÈQUE
# =========================================================

@app.route(
    "/bibliotheque",
    methods=["GET", "POST"]
)
@login_required
def library():

    # -----------------------------------------------------
    # AJOUT D'UN OUVRAGE
    # -----------------------------------------------------

    if request.method == "POST":

        if session.get("member_role") != "Administrateur":

            flash(
                "Seuls les administrateurs peuvent ajouter des ouvrages.",
                "error"
            )

            return redirect(
                url_for("library")
            )


        uploaded = request.files.get(
            "file"
        )

        title = request.form.get(
            "title",
            ""
        ).strip()

        author = request.form.get(
            "author",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()


        # Vérification du fichier

        if not uploaded or not uploaded.filename:

            flash(
                "Veuillez sélectionner un fichier.",
                "error"
            )

            return redirect(
                url_for("library")
            )


        original_name = secure_filename(
            uploaded.filename
        )


        if not original_name:

            flash(
                "Nom de fichier invalide.",
                "error"
            )

            return redirect(
                url_for("library")
            )


        if "." not in original_name:

            flash(
                "Le fichier doit posséder une extension.",
                "error"
            )

            return redirect(
                url_for("library")
            )


        extension = (
            original_name
            .rsplit(".", 1)[-1]
            .lower()
        )


        if extension not in ALLOWED_LIBRARY_EXTENSIONS:

            flash(
                "Format non autorisé. Utilisez uniquement PDF ou EPUB.",
                "error"
            )

            return redirect(
                url_for("library")
            )


        if not title or not category:

            flash(
                "Le titre et la catégorie sont obligatoires.",
                "error"
            )

            return redirect(
                url_for("library")
            )


        # -------------------------------------------------
        # NOM INTERNE DU FICHIER
        # -------------------------------------------------

        stored_name = (
            f"{uuid.uuid4().hex}.{extension}"
        )


        library_folder = (
            app.config["LIBRARY_FOLDER"]
        )

        library_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        file_path = (
            library_folder / stored_name
        )


        # Enregistrement du fichier

        uploaded.save(
            file_path
        )


        # -------------------------------------------------
        # ENREGISTREMENT EN BASE
        # -------------------------------------------------

        try:

            db().execute(
                """
                INSERT INTO library_items
                (
                    title,
                    author,
                    category,
                    description,
                    stored_name,
                    original_name,
                    file_extension
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    author,
                    category,
                    description,
                    stored_name,
                    original_name,
                    extension
                )
            )

            db().commit()


        except Exception:

            # Si la base échoue,
            # on supprime le fichier déjà envoyé.

            if file_path.exists():
                file_path.unlink()

            raise


        flash(
            "Ouvrage ajouté à la bibliothèque privée.",
            "success"
        )


        return redirect(
            url_for("library")
        )


    # -----------------------------------------------------
    # LISTE DES OUVRAGES
    # -----------------------------------------------------

    items = db().execute(
        """
        SELECT *
        FROM library_items
        ORDER BY added_at DESC
        """
    ).fetchall()


    return render_template(
        "library.html",
        items=items
    )


# =========================================================
# LECTURE D'UN OUVRAGE
# =========================================================

@app.get(
    "/bibliotheque/lire/<int:item_id>"
)
@login_required
def read_library_item(item_id):

    item = db().execute(
        """
        SELECT *
        FROM library_items
        WHERE id=?
        """,
        (item_id,)
    ).fetchone()


    if item is None:

        flash(
            "Ouvrage introuvable.",
            "error"
        )

        return redirect(
            url_for("library")
        )


    return render_template(
        "library_reader.html",
        item=item
    )


# =========================================================
# SERVIR LE FICHIER POUR LA LECTURE
# =========================================================

@app.get(
    "/bibliotheque/fichier/<int:item_id>"
)
@login_required
def library_file(item_id):

    item = db().execute(
        """
        SELECT stored_name, original_name
        FROM library_items
        WHERE id=?
        """,
        (item_id,)
    ).fetchone()


    if item is None:

        return "Ouvrage introuvable", 404


    return send_from_directory(
        app.config["LIBRARY_FOLDER"],
        item["stored_name"],
        as_attachment=False
    )


# =========================================================
# TÉLÉCHARGEMENT
# =========================================================

@app.get(
    "/bibliotheque/telecharger/<int:item_id>"
)
@login_required
def download_library_item(item_id):

    item = db().execute(
        """
        SELECT stored_name, original_name
        FROM library_items
        WHERE id=?
        """,
        (item_id,)
    ).fetchone()


    if item is None:

        return "Ouvrage introuvable", 404


    return send_from_directory(
        app.config["LIBRARY_FOLDER"],
        item["stored_name"],
        as_attachment=True,
        download_name=item["original_name"]
    )


# =========================================================
# SUPPRESSION D'UN OUVRAGE
# =========================================================

@app.post(
    "/bibliotheque/supprimer/<int:item_id>"
)
@login_required
@admin_required
def delete_library_item(item_id):

    item = db().execute(
        """
        SELECT stored_name
        FROM library_items
        WHERE id=?
        """,
        (item_id,)
    ).fetchone()


    if item is None:

        flash(
            "Ouvrage introuvable.",
            "error"
        )

        return redirect(
            url_for("library")
        )


    # Suppression du fichier

    file_path = (
        app.config["LIBRARY_FOLDER"]
        / item["stored_name"]
    )


    if file_path.exists():
        file_path.unlink()


    # Suppression de la base

    db().execute(
        """
        DELETE FROM library_items
        WHERE id=?
        """,
        (item_id,)
    )

    db().commit()


    flash(
        "Ouvrage supprimé de la bibliothèque.",
        "success"
    )


    return redirect(
        url_for("library")
    )


# =========================================================
# LANCEMENT
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )