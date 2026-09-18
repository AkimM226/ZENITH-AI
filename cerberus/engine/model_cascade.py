"""
CERBERUS - Cascade de Modèles Gemini (Addendum 6)
Gère la bascule automatique entre différents modèles Gemini en cas d'échec.
"""
from typing import Optional, Callable, Any
from cerberus.database.repository import Repository


class ModelCascade:
    """
    Gère la cascade de modèles Gemini avec verrouillage pour la durée d'un échange.
    Cascade : gemini-3.6-flash → gemini-3.7-flash → gemini-3.5-flash → gemini-flash-latest
    """

    MODEL_CASCADE = [
        "gemini-2.0-flash-exp",  # Modèle le plus récent
        "gemini-1.5-flash",       # Modèle stable
        "gemini-1.5-flash-8b",   # Modèle léger
        "gemini-1.5-flash-lite"  # Fallback le plus léger
    ]

    def __init__(self, repo: Optional[Repository] = None):
        self.repo = repo or Repository()
        self._locked_model: Optional[str] = None  # Modèle verrouillé pour l'échange actuel

    def lock_model(self, model: str):
        """Verrouille le modèle pour la durée de l'échange conversationnel."""
        self._locked_model = model

    def unlock_model(self):
        """Libère le verrou sur le modèle."""
        self._locked_model = None

    def get_current_model(self) -> str:
        """Retourne le modèle verrouillé ou le premier de la cascade."""
        return self._locked_model if self._locked_model else self.MODEL_CASCADE[0]

    def execute_with_cascade(
        self,
        callable_func: Callable[[str], Any],
        operation_name: str = "gemini_call"
    ) -> tuple[Optional[Any], Optional[str]]:
        """
        Exécute une fonction avec cascade de modèles en cas d'échec.

        Args:
            callable_func: Fonction qui prend un nom de modèle en paramètre et retourne un résultat
            operation_name: Nom de l'opération pour le logging

        Returns:
            Tuple (résultat, modèle_utilisé) ou (None, None) si échec total
        """
        # Si un modèle est verrouillé, l'utiliser uniquement
        if self._locked_model:
            try:
                result = callable_func(self._locked_model)
                return result, self._locked_model
            except Exception as e:
                # Log l'échec mais ne pas basculer si verrouillé
                self._log_model_switch(
                    operation_name,
                    self._locked_model,
                    None,
                    f"Échec avec modèle verrouillé : {str(e)}"
                )
                return None, None

        # Sinon, essayer la cascade complète
        last_error = None
        for model in self.MODEL_CASCADE:
            try:
                result = callable_func(model)
                # Log le succès si ce n'est pas le premier modèle
                if model != self.MODEL_CASCADE[0]:
                    self._log_model_switch(
                        operation_name,
                        self.MODEL_CASCADE[0],
                        model,
                        f"Bascule réussie après échec de {self.MODEL_CASCADE[0]}"
                    )
                return result, model
            except Exception as e:
                last_error = e
                # Continuer avec le modèle suivant
                continue

        # Échec total de la cascade
        self._log_model_switch(
            operation_name,
            self.MODEL_CASCADE[0],
            None,
            f"Échec total de la cascade : {str(last_error)}"
        )
        return None, None

    def _log_model_switch(self, operation: str, from_model: str, to_model: Optional[str], reason: str):
        """Journalise les bascules de modèles dans le journal de décisions."""
        try:
            self.repo.log_decision(
                type_action="MODEL_CASCADE",
                regles_appliquees=[f"Cascade Gemini : {operation}"],
                resultat="MODEL_SWITCH" if to_model else "CASCADE_FAILURE",
                details=f"Modèle initial: {from_model} → Modèle final: {to_model or 'AUCUN'}. Raison: {reason}"
            )
        except Exception:
            # Ne pas échouer si le logging échoue
            pass

    def __enter__(self):
        """Context manager pour verrouiller automatiquement un modèle."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Libère le verrou à la sortie du contexte."""
        self.unlock_model()
        return False


# Instance globale pour réutilisation
_global_cascade: Optional[ModelCascade] = None


def get_model_cascade(repo: Optional[Repository] = None) -> ModelCascade:
    """Retourne l'instance globale de la cascade de modèles."""
    global _global_cascade
    if _global_cascade is None:
        _global_cascade = ModelCascade(repo)
    return _global_cascade