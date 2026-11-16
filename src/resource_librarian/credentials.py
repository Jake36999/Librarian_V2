"""Conservative path-only refusal, before content reads or model dispatch."""
from pathlib import PurePosixPath


# Secret stores by name (2026-11-16: an archived Geo-Grapher QA folder held fifteen
# `*.sqlite.cursor-secret` files the earlier rules let through). Exact names, so a code file
# such as `credentials.py` or a paper about secret sharing is never refused.
SECRET_SUFFIXES = ('.secret', '-secret', '_secret', '.secrets')
SECRET_NAMES = frozenset({'secrets', 'secrets.json', 'secrets.yaml', 'secrets.yml', 'secrets.toml',
                          'credentials', 'credentials.json', '.netrc', '.pgpass', '.htpasswd'})


def credential_path(path) -> bool:
    for raw in PurePosixPath(str(path).replace('\\', '/')).parts:
        name = raw.casefold()
        if (name == 'certs' or name == '.env' or name.endswith('.env')
                or name.startswith(('.env.', 'id_'))
                or name.endswith(('.key', '.pem', '.p12', '.pfx'))
                or name.endswith(SECRET_SUFFIXES) or name in SECRET_NAMES):
            return True
    return False


def refuse_credentials(path):
    if credential_path(path):
        raise ValueError(f'CREDENTIAL_REFUSED: {path}')


def generated_path(path) -> bool:
    """Path-only generated-build hygiene, before survey/index content reads."""
    p = PurePosixPath(str(path).replace('\\', '/'))
    return (bool({'dist', 'build', '.next', '.nuxt', 'coverage', 'graphify-out'}.intersection(p.parts))
        or ('/resource_librarian/ui/' in '/' + p.as_posix() and p.suffix == '.js')
        or p.name.endswith(('.bundle.js', '.min.js', '.js.map')))
