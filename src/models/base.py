"""Base model module providing abstract base class for all models."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from datetime import datetime
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.exceptions import ModelError, ModelNotFittedError, ModelValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T')
PredictionType = TypeVar('PredictionType')
FeatureType = TypeVar('FeatureType')


class BaseModel(ABC, Generic[FeatureType, PredictionType]):
    """Abstract base class for all machine learning models.
    
    This class provides the foundation for implementing machine learning models
    with standardized interfaces for training, prediction, serialization, and
    validation.
    
    Attributes:
        fitted (bool): Whether the model has been fitted.
        feature_names (Optional[List[str]]): Names of features used in training.
        training_date (Optional[datetime]): Timestamp when model was last trained.
        model_params (Dict[str, Any]): Model hyperparameters.
        metadata (Dict[str, Any]): Additional model metadata.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the base model.
        
        Args:
            **kwargs: Model hyperparameters and configuration.
            
        Raises:
            ModelValidationError: If invalid parameters are provided.
        """
        self.fitted: bool = False
        self.feature_names: Optional[List[str]] = None
        self.training_date: Optional[datetime] = None
        self.model_params: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {
            'model_type': self.__class__.__name__,
            'created_at': datetime.now().isoformat(),
            'version': '1.0.0'
        }
        
        try:
            self._validate_params(**kwargs)
            self.model_params.update(kwargs)
        except Exception as e:
            raise ModelValidationError(f"Invalid model parameters: {e}") from e

    @abstractmethod
    def _validate_params(self, **kwargs: Any) -> None:
        """Validate model parameters.
        
        Args:
            **kwargs: Parameters to validate.
            
        Raises:
            ModelValidationError: If parameters are invalid.
        """
        pass

    @abstractmethod
    def fit(self, X: FeatureType, y: Optional[Union[pd.Series, np.ndarray]] = None, **kwargs: Any) -> 'BaseModel':
        """Fit the model to training data.
        
        Args:
            X: Training features.
            y: Target values (optional for unsupervised learning).
            **kwargs: Additional fitting parameters.
            
        Returns:
            Self for method chaining.
            
        Raises:
            ModelValidationError: If input data is invalid.
            ModelError: If fitting fails.
        """
        pass

    @abstractmethod
    def predict(self, X: FeatureType, **kwargs: Any) -> PredictionType:
        """Make predictions using the fitted model.
        
        Args:
            X: Features to predict on.
            **kwargs: Additional prediction parameters.
            
        Returns:
            Predictions.
            
        Raises:
            ModelNotFittedError: If model hasn't been fitted.
            ModelValidationError: If input data is invalid.
            ModelError: If prediction fails.
        """
        pass

    def predict_proba(self, X: FeatureType, **kwargs: Any) -> np.ndarray:
        """Predict class probabilities.
        
        Args:
            X: Features to predict on.
            **kwargs: Additional prediction parameters.
            
        Returns:
            Array of shape (n_samples, n_classes) with probability estimates.
            
        Raises:
            ModelNotFittedError: If model hasn't been fitted.
            NotImplementedError: If model doesn't support probability predictions.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support probability predictions")

    def score(self, X: FeatureType, y: Union[pd.Series, np.ndarray], **kwargs: Any) -> float:
        """Calculate model performance score.
        
        Args:
            X: Test features.
            y: True target values.
            **kwargs: Additional scoring parameters.
            
        Returns:
            Performance score.
            
        Raises:
            ModelNotFittedError: If model hasn't been fitted.
            ModelValidationError: If input data is invalid.
        """
        if not self.fitted:
            raise ModelNotFittedError("Model must be fitted before scoring")
        
        try:
            predictions = self.predict(X, **kwargs)
            return self._calculate_score(y, predictions)
        except Exception as e:
            raise ModelError(f"Failed to calculate model score: {e}") from e

    @abstractmethod
    def _calculate_score(self, y_true: Union[pd.Series, np.ndarray], 
                        y_pred: PredictionType) -> float:
        """Calculate model performance metric.
        
        Args:
            y_true: True target values.
            y_pred: Predicted values.
            
        Returns:
            Performance score.
        """
        pass

    def save(self, filepath: Union[str, Path]) -> None:
        """Save model to disk.
        
        Args:
            filepath: Path to save the model.
            
        Raises:
            ModelError: If saving fails.
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = self._serialize()
            
            with open(filepath, 'w') as f:
                json.dump(model_data, f, indent=2, default=str)
            
            logger.info(f"Model saved to {filepath}")
        except Exception as e:
            raise ModelError(f"Failed to save model to {filepath}: {e}") from e

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> 'BaseModel':
        """Load model from disk.
        
        Args:
            filepath: Path to load the model from.
            
        Returns:
            Loaded model instance.
            
        Raises:
            ModelError: If loading fails.
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                raise FileNotFoundError(f"Model file not found: {filepath}")
            
            with open(filepath, 'r') as f:
                model_data = json.load(f)
            
            model = cls(**model_data.get('model_params', {}))
            model._deserialize(model_data)
            
            logger.info(f"Model loaded from {filepath}")
            return model
        except Exception as e:
            raise ModelError(f"Failed to load model from {filepath}: {e}") from e

    def _serialize(self) -> Dict[str, Any]:
        """Serialize model to dictionary.
        
        Returns:
            Dictionary containing model data.
        """
        return {
            'model_type': self.__class__.__name__,
            'fitted': self.fitted,
            'feature_names': self.feature_names,
            'training_date': self.training_date.isoformat() if self.training_date else None,
            'model_params': self.model_params,
            'metadata': self.metadata
        }

    def _deserialize(self, data: Dict[str, Any]) -> None:
        """Deserialize model from dictionary.
        
        Args:
            data: Dictionary containing model data.
        """
        self.fitted = data.get('fitted', False)
        self.feature_names = data.get('feature_names')
        
        training_date = data.get('training_date')
        if training_date:
            self.training_date = datetime.fromisoformat(training_date)
        
        self.model_params = data.get('model_params', {})
        self.metadata = data.get('metadata', {})

    def get_params(self) -> Dict[str, Any]:
        """Get model parameters.
        
        Returns:
            Dictionary of model parameters.
        """
        return self.model_params.copy()

    def set_params(self, **params: Any) -> 'BaseModel':
        """Set model parameters.
        
        Args:
            **params: Parameters to set.
            
        Returns:
            Self for method chaining.
            
        Raises:
            ModelValidationError: If parameters are invalid.
        """
        try:
            self._validate_params(**params)
            self.model_params.update(params)
            return self
        except Exception as e:
            raise ModelValidationError(f"Invalid parameters: {e}") from e

    def is_fitted(self) -> bool:
        """Check if model has been fitted.
        
        Returns:
            True if model is fitted, False otherwise.
        """
        return self.fitted

    def __repr__(self) -> str:
        """String representation of the model.
        
        Returns:
            String representation.
        """
        params_str = ', '.join(f"{k}={v}" for k, v in self.model_params.items())
        return f"{self.__class__.__name__}(fitted={self.fitted}, {params_str})"

    def __str__(self) -> str:
        """Human-readable string representation.
        
        Returns:
            String representation.
        """
        return f"{self.__class__.__name__} Model (fitted: {self.fitted})"

    def __getstate__(self) -> Dict[str, Any]:
        """Prepare model for pickling.
        
        Returns:
            Dictionary of picklable attributes.
        """
        return self._serialize()

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Restore model from pickled state.
        
        Args:
            state: Dictionary of pickled attributes.
        """
        self._deserialize(state)