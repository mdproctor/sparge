package io.sparge.server;

/**
 * A single validation issue from MdValidator — mirrors md_validator.py Issue dataclass.
 * level is "ERROR" or "WARN".
 */
public record MdIssue(String check, String level, String detail) {

    @Override
    public String toString() {
        return "[" + level + "] " + check + ": " + detail;
    }
}
