# PODA Packaging Lessons

## What Broke First

- The app was not portable when it depended on system Java.
- Oracle connectivity failed on another machine even though the installer existed.
- The fix was to bundle a runtime Java with `jlink`.

## What The Bundle Needs

- `dist\PODA\PODA.exe`
- `dist\PODA\jre`
- `jdbc\ojdbc8.jar`
- `%APPDATA%\PODA\.env` on the target machine

## Java Runtime Modules

The portable runtime has to include at least:

- `java.base`
- `java.sql`
- `java.naming`
- `java.management`
- `java.security.jgss`
- `java.security.sasl`
- `jdk.zipfs`

Without `jdk.zipfs`, JPype can fail when loading the JDBC jar.
Without the security modules, Oracle JDBC can fail during authentication.

## Config Rules

- `ORACLE_TARGETS` is editable.
- `ORACLE_PASSWORD` stays out of the installer defaults.
- The installer seeds `%APPDATA%\PODA\.env` only if it does not already exist.
- GUI changes should save back to `%APPDATA%\PODA\.env`.

## Naming Rules

- `DIG_ID_GENERACION` is the Oracle filter.
- The ISSFA tramite number is a separate value used for the output folder name.
- Output artifacts should be named from the ISSFA tramite number, not from the filter.

## Release Check

Before sharing a build:

1. Rebuild.
2. Test Oracle on the build machine.
3. Verify the packaged `jre` exists in the output.
4. Install on a clean machine if portability is the goal.

