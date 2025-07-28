import { useState } from 'react'

interface LoadingState {
  isLoading: boolean
  error: string | null
}

export function useLoadingState(id: string) {
  const [state, setState] = useState<LoadingState>({
    isLoading: false,
    error: null
  });

  const setLoading = (isLoading: boolean) => {
    setState(prevState => ({ ...prevState, isLoading }));
  };

  const setError = (error: string | null) => {
    setState(prevState => ({ ...prevState, error }));
  };

  return { state, setLoading, setError };
}
