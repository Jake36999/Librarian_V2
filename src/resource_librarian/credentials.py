"""Conservative path-only refusal, before content reads or model dispatch."""
from pathlib import PurePosixPath


def credential_path(path) -> bool:
    for raw in PurePosixPath(str(path).replace('\\', '/')).parts:
        name = raw.casefold()
        if (name == 'certs' or name == '.env' or name.endswith('.env')
                or name.startswith(('.env.', 'id_'))
                or name.endswith(('.key', '.pem', '.p12', '.pfx'))):
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
