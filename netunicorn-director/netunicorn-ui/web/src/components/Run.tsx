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
import { Pipeline, getPipelines, getNodes, Node } from "../api/api-requests.ts";

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

  const handleRunExperiments = () => {
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
            <div
              key={index}
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                marginBottom: "10px",
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
                  style={{ marginRight: "10px" }}
                >
                  {pipelineOptions.map((option, idx) => (
                    <MenuItem key={idx} value={option.name}>
                      {option.name}
                      {option.description}
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
                    <MenuItem key={idx} value={node.name}>
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