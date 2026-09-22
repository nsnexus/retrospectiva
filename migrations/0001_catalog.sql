CREATE TABLE IF NOT EXISTS cities (normalized TEXT NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, PRIMARY KEY(normalized,state));
CREATE TABLE IF NOT EXISTS companies (cnpj TEXT PRIMARY KEY, name TEXT NOT NULL, cnae TEXT NOT NULL, sector TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL, address TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL, opened TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, search TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS companies_geo ON companies(lat,lng);
CREATE INDEX IF NOT EXISTS companies_cnae ON companies(cnae);
CREATE INDEX IF NOT EXISTS companies_opened ON companies(opened);
