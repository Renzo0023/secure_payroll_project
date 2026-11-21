<?php

declare(strict_types=1);

namespace Lab\Vulnerable;

/*
 * ============================================================================================
 *  CODE VOLONTAIREMENT VULNÉRABLE — PHASES 4 ET 5 (analyse et remédiation contrôlées)
 *  Ne jamais copier ce code dans app/. Chargé uniquement par App\Security\LabMode, dans une
 *  instance de laboratoire jetable (/tmp/securepayroll-lab-*) servie par `php -S`.
 *  Version corrigée : app/Access/AccessHistory.php.
 * ============================================================================================
 */

if (!class_exists(\App\Security\LabMode::class) || !\App\Security\LabMode::vulnerableAccessHistory()) {
    http_response_code(404);
    exit;
}

final class VulnerableAccessHistory
{
    /**
     * Phase 5 : une seule des trois défenses de code réactivée, pour mesurer son effet isolé.
     *  - vulnerable       : aucune (version de la phase 4)
     *  - prepared-only    : requête préparée, mais ni validation ni masquage des erreurs
     *  - validation-only  : validation stricte de la date, mais concaténation et erreurs brutes
     *  - generic-errors   : message d'erreur générique, mais concaténation et aucune validation
     *
     * @return array{rows: list<list<mixed>>, error: ?string, status: int}
     */
    public static function searchVariant(\PDO $db, int $accountId, string $since, string $variant): array
    {
        if ($variant === 'prepared-only') {
            // Contrôle isolé : la saisie voyage comme une VALEUR, séparée du texte de la requête.
            $query = $db->prepare('SELECT r.code, ra.valid_from, ra.expires_at, ra.revoked_at FROM role_assignments ra '
                . 'JOIN roles r ON r.id = ra.role_id WHERE ra.account_id = ? AND ra.valid_from >= ? ORDER BY ra.valid_from DESC');
            try {
                $query->execute([$accountId, $since]);
                return ['rows' => $query->fetchAll(\PDO::FETCH_NUM), 'error' => null, 'status' => 200];
            } catch (\PDOException $exception) {
                return ['rows' => [], 'error' => $exception->getMessage(), 'status' => 200];
            }
        }
        if ($variant === 'validation-only') {
            // Contrôle isolé : liste blanche stricte AAAA-MM-JJ ; la requête reste concaténée.
            $date = \App\Access\AccessHistory::parseDate($since);
            if ($date === null) {
                return ['rows' => [], 'error' => t('access.invalid_date'), 'status' => 422];
            }
            return self::search($db, $accountId, $date) + ['status' => 200];
        }
        $result = self::search($db, $accountId, $since);
        if ($variant === 'generic-errors' && $result['error'] !== null) {
            // Contrôle isolé : le détail du SGBD est caché ; la requête reste injectable.
            $result['error'] = t('access.lab_generic_error');
        }
        return $result + ['status' => 200];
    }

    /** @return array{rows: list<list<mixed>>, error: ?string} */
    public static function search(\PDO $db, int $accountId, string $since): array
    {
        // FAIBLESSE 1 — aucune validation côté serveur : seul le champ <input type="date"> du
        // navigateur « contrôle » la saisie, et il suffit de modifier l'URL pour le contourner.
        // FAIBLESSE 2 — la saisie est concaténée dans le texte de la requête SQL : une apostrophe
        // ferme la chaîne et la suite est interprétée comme du SQL.
        $sql = "SELECT r.code, ra.valid_from, ra.expires_at, ra.revoked_at FROM role_assignments ra "
            . "JOIN roles r ON r.id = ra.role_id WHERE ra.account_id = " . $accountId
            . " AND ra.valid_from >= '" . $since . "' ORDER BY ra.valid_from DESC";
        try {
            return ['rows' => $db->query($sql)->fetchAll(\PDO::FETCH_NUM), 'error' => null];
        } catch (\PDOException $exception) {
            // FAIBLESSE 3 — le message d'erreur du SGBD est renvoyé à l'utilisateur : il révèle la
            // structure de la requête et guide l'attaquant.
            return ['rows' => [], 'error' => $exception->getMessage()];
        }
    }
}
