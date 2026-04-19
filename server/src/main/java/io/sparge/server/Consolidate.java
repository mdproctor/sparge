package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Hash-based asset consolidation — port of scripts/consolidate.py.
 *
 * Finds files with identical SHA-256 across different post folders, promotes
 * the first to assets/global/, deletes duplicates, updates .url-index.json,
 * and rewrites HTML references in the cleaned HTML directory.
 */
public final class Consolidate {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private Consolidate() {}

    public record Result(int promoted, int updatedHtml, List<Map<String, Object>> duplicates) {}

    /**
     * Main entry point — mirrors consolidate.py consolidate().
     *
     * @param assetsRoot  the assets/ directory (contains global/ and posts/)
     * @param cleanedDir  directory of HTML files whose asset references get rewritten
     */
    public static Result consolidate(Path assetsRoot, Path cleanedDir) throws Exception {
        Path indexFile = assetsRoot.resolve(".url-index.json");
        Map<String, String> index = loadIndex(indexFile);

        // Build hash → [path] map across all post folders
        Map<String, List<Path>> hashToPaths = new LinkedHashMap<>();
        Path postsDir = assetsRoot.resolve("posts");
        if (Files.isDirectory(postsDir)) {
            try (var slugDirs = Files.newDirectoryStream(postsDir)) {
                for (Path slugDir : slugDirs) {
                    if (!Files.isDirectory(slugDir)) continue;
                    try (var files = Files.newDirectoryStream(slugDir)) {
                        for (Path file : files) {
                            if (Files.isRegularFile(file)) {
                                String hash = fileHash(file);
                                hashToPaths.computeIfAbsent(hash, k -> new ArrayList<>()).add(file);
                            }
                        }
                    }
                }
            }
        }

        int promoted = 0;
        List<Map<String, Object>> duplicates = new ArrayList<>();
        Map<Path, Path> globalMap = new LinkedHashMap<>(); // old → new global path

        for (Map.Entry<String, List<Path>> entry : hashToPaths.entrySet()) {
            String     hash  = entry.getKey();
            List<Path> paths = entry.getValue();

            // Only consolidate if the same content appears in 2+ different post folders
            Set<String> slugs = paths.stream()
                    .map(p -> p.getParent().getFileName().toString())
                    .collect(Collectors.toSet());
            if (slugs.size() < 2) continue;

            // Promote the first file to global/
            Path primary   = paths.get(0);
            Path globalDir = assetsRoot.resolve("global");
            Files.createDirectories(globalDir);
            Path newPath = uniquePath(globalDir, primary.getFileName().toString());
            Files.move(primary, newPath);

            // Update index entries pointing to the old primary path
            String oldPrimaryRel = assetsRoot.relativize(primary).toString().replace('\\', '/');
            String newRel        = assetsRoot.relativize(newPath).toString().replace('\\', '/');
            index.replaceAll((url, rel) -> rel.equals(oldPrimaryRel) ? newRel : rel);

            globalMap.put(primary, newPath);
            promoted++;

            // Remove duplicate copies
            for (Path dup : paths.subList(1, paths.size())) {
                if (Files.exists(dup)) {
                    String dupOldRel = assetsRoot.relativize(dup).toString().replace('\\', '/');
                    index.replaceAll((url, rel) -> rel.equals(dupOldRel) ? newRel : rel);
                    globalMap.put(dup, newPath);
                    Files.delete(dup);
                }
            }

            Map<String, Object> dup = new LinkedHashMap<>();
            dup.put("hash",        hash.substring(0, 12));
            dup.put("files",       paths.stream().map(Path::toString).collect(Collectors.toList()));
            dup.put("global_path", newPath.toString());
            duplicates.add(dup);
        }

        if (promoted > 0) {
            saveIndex(indexFile, index);
        }
        int updatedHtml = rewriteHtmlReferences(cleanedDir, globalMap, assetsRoot);
        return new Result(promoted, updatedHtml, duplicates);
    }

    /** SHA-256 hex of a file — matches Python's file_hash(). */
    static String fileHash(Path file) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (var in = new DigestInputStream(Files.newInputStream(file), md)) {
            byte[] buf = new byte[65536];
            while (in.read(buf) != -1) { /* drain */ }
        }
        byte[] digest = md.digest();
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    /** Return a path in dir for filename that doesn't yet exist. */
    static Path uniquePath(Path dir, String filename) throws IOException {
        Path candidate = dir.resolve(filename);
        if (!Files.exists(candidate)) return candidate;
        String base = filename.contains(".") ? filename.substring(0, filename.lastIndexOf('.')) : filename;
        String ext  = filename.contains(".") ? filename.substring(filename.lastIndexOf('.'))    : "";
        for (int i = 2; i < 1000; i++) {
            candidate = dir.resolve(base + "-" + i + ext);
            if (!Files.exists(candidate)) return candidate;
        }
        throw new IOException("Could not find unique name for: " + filename);
    }

    /**
     * Rewrite /assets/posts/… references to /assets/global/… in all HTML files.
     * Package-private for unit testing.
     */
    static int rewriteHtmlReferences(Path cleanedDir, Map<Path, Path> globalMap, Path assetsRoot) throws IOException {
        if (!Files.isDirectory(cleanedDir) || globalMap.isEmpty()) return 0;

        Map<String, String> pathRemap    = new LinkedHashMap<>();
        Map<String, String> pathRemapLC  = new LinkedHashMap<>(); // lowercase keys for case-insensitive lookup
        for (Map.Entry<Path, Path> entry : globalMap.entrySet()) {
            try {
                String oldRel = "/assets/" + assetsRoot.relativize(entry.getKey()).toString().replace('\\', '/');
                String newRel = "/assets/" + assetsRoot.relativize(entry.getValue()).toString().replace('\\', '/');
                pathRemap.put(oldRel, newRel);
                pathRemapLC.put(oldRel.toLowerCase(), newRel);
            } catch (IllegalArgumentException ignored) {}
        }
        if (pathRemap.isEmpty()) return 0;

        Pattern regex = Pattern.compile(
                pathRemap.keySet().stream().map(Pattern::quote).collect(Collectors.joining("|")),
                Pattern.CASE_INSENSITIVE);

        int updated = 0;
        List<Path> htmlFiles;
        try (var stream = Files.walk(cleanedDir)) {
            htmlFiles = stream.filter(p -> p.toString().endsWith(".html"))
                              .collect(Collectors.toList());
        }
        for (Path htmlFile : htmlFiles) {
            String text    = Files.readString(htmlFile, StandardCharsets.UTF_8);
            String newText = regex.matcher(text).replaceAll(m -> pathRemapLC.get(m.group(0).toLowerCase()));
            if (!newText.equals(text)) {
                Files.writeString(htmlFile, newText, StandardCharsets.UTF_8);
                updated++;
            }
        }
        return updated;
    }

    private static Map<String, String> loadIndex(Path indexFile) throws IOException {
        if (!Files.exists(indexFile)) return new LinkedHashMap<>();
        ObjectNode node = (ObjectNode) MAPPER.readTree(indexFile.toFile());
        Map<String, String> map = new LinkedHashMap<>();
        node.fields().forEachRemaining(e -> map.put(e.getKey(), e.getValue().asText()));
        return map;
    }

    private static void saveIndex(Path indexFile, Map<String, String> index) throws IOException {
        ObjectNode node = MAPPER.createObjectNode();
        index.forEach(node::put);
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(indexFile.toFile(), node);
    }
}
