import sqlalchemy

import config
from tables import Base


if __name__ == '__main__':  # pragma: no cover
    engine = sqlalchemy.create_engine(config.POSTGRES_DSN)
    Base.metadata.create_all(engine)
