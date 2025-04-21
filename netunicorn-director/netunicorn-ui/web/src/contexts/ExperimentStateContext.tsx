import React, { createContext, useContext, useState, PropsWithChildren } from 'react';

interface ExperimentState {
  experimentResult: any;
  setExperimentResult: React.Dispatch<React.SetStateAction<any>>;
  loading: boolean;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
}

const ExperimentStateContext = createContext<ExperimentState | undefined>(undefined); // initially undefined

export const ExperimentStateProvider: React.FC<PropsWithChildren<{}>> = ({ children }) => {
  const [experimentResult, setExperimentResult] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const value: ExperimentState = {
    experimentResult,
    setExperimentResult,
    loading,
    setLoading,
  };

  return (
    <ExperimentStateContext.Provider value={value}>
      {children}
    </ExperimentStateContext.Provider>
  );
};

export const useExperimentState = (): ExperimentState => {
  const context = useContext(ExperimentStateContext);
  if (!context) {
    throw new Error("useExperimentState must be used within an ExperimentStateProvider");
  }
  return context;
};
