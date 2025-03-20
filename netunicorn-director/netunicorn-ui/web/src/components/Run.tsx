import React, { useState, useEffect } from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import Select from "@mui/material/Select";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import Box from "@mui/material/Box";
import { Pipeline, getPipelines, getNodes, Node, ExperimentMapping, sendExperimentMapping } from "../api/api-requests.ts";
import { Typography } from "@mui/material";

interface RowData {
  pipeline: string;
  nodes: string[];
  pipelineError: string;
  nodesError: string;
}

const RunExperimentsTable: React.FC = () => {
  const [rows, setRows] = useState<RowData[]>([
    { pipeline: "", nodes: [], pipelineError: "", nodesError: "" },
  ]);
  const [pipelineOptions, setPipelineOptions] = useState<Pipeline[]>([]);
  const [nodeOptions, setNodeOptions] = useState<Node[]>([]);
  
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
        console.error("Failed to fetch locked nodes:", error);
      }
    };
    fetchData();
  }, []);

  const handleRunExperiments = async () => {
    let isValid = true;
    const updatedRows = [...rows];
  
    rows.forEach((row, i) => {
      if (row.pipeline === "") {
        updatedRows[i].pipelineError = "Select a Pipeline";
        isValid = false;
      }
      if (row.nodes.length === 0) {
        updatedRows[i].nodesError = "Select at least one Node";
        isValid = false;
      }
    });
  
    if (!isValid) {
      setRows(updatedRows);
      return;
    }
  
    console.log("Pipeline Options:", pipelineOptions);
    console.log("Node Options:", nodeOptions);

    const experimentMappings = rows.map(row => {
      const pipeline = pipelineOptions.find(p => p.name === row.pipeline);
      if (!pipeline) {
        throw new Error(`Pipeline ${row.pipeline} not found in pipelineOptions`);
      }
  
      const selectedNodes = nodeOptions.filter(n => row.nodes.includes(n.name));
      return {
        pipelines: pipeline,
        nodes: selectedNodes,
      };
    });
  
    console.log("Experiment Mapping(s):", experimentMappings);
  
    try {
      for (const mapping of experimentMappings) {
        await sendExperimentMapping(mapping);
      }
      console.log("All experiment mappings sent successfully.");
    } catch (error) {
      console.error("Error sending experiment mapping:", error);
    }
  };  

  const handleAddRow = (index: number) => {
    const updatedRows = [...rows];
    updatedRows.splice(index + 1, 0, {
      pipeline: "",
      nodes: [],
      pipelineError: "",
      nodesError: "",
    });
    setRows(updatedRows);
  };

  const handleDeleteRow = (index: number) => {
    setRows(rows.filter((_, i) => i !== index));
  };

  const handleDropdownChange = (index: number, col: string, value: any) => {
    const updatedRows = rows.map((row, i) =>
      i === index ? { ...row, [col]: value, [`${col}Error`]: "" } : row
    );
    setRows(updatedRows);
  };

  const experiments = () => {
    let changed = true;
    const updatedRows = [...rows];
    rows.forEach((row, i) => {
      if (row.pipeline === "") {
        updatedRows[i].pipelineError = "Select a Pipeline";
        changed = false;
      }
      if (row.nodes.length === 0) {
        updatedRows[i].nodesError = "Select at least one Node";
        changed = false;
      }
    });
    if (!changed) {
      setRows(updatedRows);
      return;
    }

    console.log(rows);
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        paddingTop: 2,
      }}
    >
      <h1 style={{ paddingBottom: 10 }}>Run Experiments</h1>
      <Box
        sx={{
          width: "100%",
          maxWidth: 800,
          minWidth: 400,
          padding: 4,
          backgroundColor: "white",
          display: "flex",
          flexDirection: "column",
          borderRadius: 2,
          boxShadow: 3,
        }}
      >
        {rows.map((row, index) => {
          const error = row.pipelineError !== "" || row.nodesError !== "";
          return (
            <div key={index}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <IconButton
                  onClick={() => handleAddRow(index)}
                  style={{
                    backgroundColor: "lightblue",
                    color: "white",
                    marginRight: "10px",
                    marginBottom: error ? "23px" : 0,
                  }}
                >
                  <AddIcon />
                </IconButton>
                <FormControl fullWidth>
                  <InputLabel>Pipeline</InputLabel>
                  <Select
                    label="Pipeline"
                    error={row.pipelineError !== ""}
                    value={row.pipeline}
                    onChange={(e) =>
                      handleDropdownChange(index, "pipeline", e.target.value)
                    }
                    renderValue={(selected) => {
                      return row.pipeline;
                    }}
                    style={{ marginRight: "10px" }}
                  >
                    {pipelineOptions.map((option, idx) => (
                      <MenuItem key={idx} value={option.name} sx={{ width: "350px"}}>
                        <div style={{ display: "flex", flexDirection: "column" }}>

                        <Typography 
                          variant="body1" 
                          sx={{ whiteSpace: "normal", wordWrap: "break-word" }}>
                            {option.name}
                        </Typography>
                        <Typography 
                          variant="body2" 
                          color="gray" 
                          sx={{ whiteSpace: "normal", wordWrap: "break-word" }}>
                            {option.description}
                        </Typography>
                        </div>
                      </MenuItem>
                    ))}
                  </Select>
                  {row.pipelineError && (
                    <FormHelperText sx={{ color: "red" }}>
                      {row.pipelineError}
                    </FormHelperText>
                  )}
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel>Nodes</InputLabel>
                  <Select
                    label="Nodes"
                    error={row.nodesError !== ""}
                    multiple
                    value={row.nodes}
                    onChange={(e) =>
                      handleDropdownChange(index, "nodes", e.target.value)
                    }
                    style={{ marginRight: "10px" }}
                  >
                    {nodeOptions.map((node, idx) => (
                      <MenuItem key={idx} value={node.name} sx={{ width: "350px"}}>
                        {node.name}
                      </MenuItem>
                    ))}
                  </Select>
                  {row.nodesError && (
                    <FormHelperText sx={{ color: "red" }}>
                      {row.nodesError}
                    </FormHelperText>
                  )}
                </FormControl>
                <IconButton
                  disabled={rows.length <= 1}
                  onClick={() => handleDeleteRow(index)}
                  style={{
                    backgroundColor: rows.length <= 1 ? "gray" : "red",
                    color: "white",
                    marginRight: "10px",
                    marginBottom: error ? "23px" : 0,
                  }}
                >
                  <DeleteIcon />
                </IconButton>
              </div>

              {pipelineOptions.find(pipeline => pipeline.name === row.pipeline) && (
                <div
                  style={{
                    display: 'flex',
                    justifyContent: "space-between",
                    alignItems: 'center',
                    marginTop: '20px',
                    marginBottom: '20px',
                    marginLeft: '60px',
                    paddingRight: '60px'
                  }}
                >
                  <div style={{ textAlign: "left", flex: 1 }}>
                    <Typography variant="body2" component="span" fontWeight="bold">
                      Pipeline Description:{" "}
                    </Typography>
                    <Typography variant="body2">
                      {pipelineOptions.find(pipeline => pipeline.name === row.pipeline)?.description}
                    </Typography>
                  </div>
                </div>
              )}

            </div>
          );
        })}
        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <Button
            variant="contained"
            color="primary"
            size="large"
            onClick={handleRunExperiments}
            style={{
              marginTop: "10px",
              border: "none",
            }}
          >
            Run Experiments
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

const Run: React.FC = () => {
  return (
    <div>
      <RunExperimentsTable />
    </div>
  );
};

export default Run;