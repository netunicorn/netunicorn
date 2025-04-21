import React, { useState, useEffect } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import {
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  FormHelperText,
  Typography,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  Pipeline,
  Node,
  ExperimentMapping,
  getPipelines,
  getNodes,
  sendExperimentMapping,
} from '../api/api-requests.ts';
import { useExperimentState } from '../contexts/ExperimentStateContext.tsx';

const RunExperiments: React.FC = () => {
  // State for user inputs remains local.
  const [selectedPipeline, setSelectedPipeline] = useState<string>("");
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);
  const [pipelineError, setPipelineError] = useState<string>("");
  const [nodesError, setNodesError] = useState<string>("");

  const [pipelineOptions, setPipelineOptions] = useState<Pipeline[]>([]);
  const [nodeOptions, setNodeOptions] = useState<Node[]>([]);

  // Retrieve global states
  const { experimentResult, setExperimentResult, loading, setLoading } = useExperimentState();
  const [notification, setNotification] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const pipelines = await getPipelines();
        setPipelineOptions(pipelines);
      } catch (error) {
        console.error("Failed to fetch pipelines:", error);
      }
      try {
        const nodes = await getNodes();
        setNodeOptions(nodes);
      } catch (error) {
        console.error("Failed to fetch nodes:", error);
      }
    };
    fetchData();
  }, []);

  const handleRunExperiments = async () => {
    let valid = true;
    if (selectedPipeline === "") {
      setPipelineError("Select a Pipeline");
      valid = false;
    }
    if (selectedNodes.length === 0) {
      setNodesError("Select at least one Node");
      valid = false;
    }
    if (!valid) return;

    const pipelineObj = pipelineOptions.find((p) => p.short_name === selectedPipeline);
    if (!pipelineObj) {
      console.error(`Pipeline ${selectedPipeline} not found.`);
      return;
    }

    const nodesList = nodeOptions.filter((n) => selectedNodes.includes(n.name));
    const experimentMapping: ExperimentMapping = {
      pipeline: pipelineObj,
      nodes: nodesList,
    };

    console.log("Experiment Mapping:", experimentMapping);

    setLoading(true);
    setNotification(null);
    try {
      const result = await sendExperimentMapping(experimentMapping);
      setExperimentResult(result); // Set in global context
      setNotification({ message: "Experiment mapping ran successfully.", severity: "success" });
      console.log("Experiment mapping sent successfully.");
    } catch (error: any) {
      console.error("Error sending experiment mapping:", error);
      setNotification({ message: "Error running experiment mapping.", severity: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ width: "100%", maxWidth: 800, minWidth: 400, padding: 4, backgroundColor: "white", borderRadius: 2, boxShadow: 3, margin: "auto", mt: 4 }}>
      <Typography variant="h4" sx={{ mb: 2 }}>
        Run Experiments
      </Typography>

      {notification && (
        <Alert severity={notification.severity} sx={{ mb: 2 }}>
          {notification.message}
        </Alert>
      )}

      <FormControl fullWidth error={Boolean(pipelineError)} sx={{ mb: 2 }}>
        <InputLabel>Pipeline</InputLabel>
        <Select
          label="Pipeline"
          value={selectedPipeline}
          onChange={(e) => {
            setSelectedPipeline(e.target.value as string);
            setPipelineError("");
          }}
        >
          {pipelineOptions.map((option) => (
            <MenuItem key={option.short_name} value={option.short_name}>
              {option.short_name}
            </MenuItem>
          ))}
        </Select>
        {pipelineError && <FormHelperText>{pipelineError}</FormHelperText>}
      </FormControl>

      <FormControl fullWidth error={Boolean(nodesError)} sx={{ mb: 2 }}>
        <InputLabel>Nodes</InputLabel>
        <Select
          label="Nodes"
          multiple
          value={selectedNodes}
          onChange={(e) => {
            setSelectedNodes(e.target.value as string[]);
            setNodesError("");
          }}
        >
          {nodeOptions.map((node) => (
            <MenuItem key={node.name} value={node.name}>
              {node.name}
            </MenuItem>
          ))}
        </Select>
        {nodesError && <FormHelperText>{nodesError}</FormHelperText>}
      </FormControl>

      <Button variant="contained" onClick={handleRunExperiments}>
        Run Experiment
      </Button>

      {loading && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
          <CircularProgress />
        </Box>
      )}

      {experimentResult && !loading && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6">Output:</Typography>
          <pre style={{ backgroundColor: "#f5f5f5", padding: "10px", borderRadius: "4px" }}>
            {JSON.stringify(experimentResult[0], null, 2)}
          </pre>
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography>Full Output</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <pre style={{ backgroundColor: "#f5f5f5", padding: "10px", borderRadius: "4px" }}>
                {JSON.stringify(experimentResult[1], null, 2)}
              </pre>
            </AccordionDetails>
          </Accordion>
        </Box>
      )}
    </Box>
  );
};

export default RunExperiments;