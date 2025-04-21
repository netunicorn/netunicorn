import axios, { AxiosInstance, AxiosError } from 'axios';
import { NETUNICORN_MEDIATOR_URL } from '../globals.ts';

// TS Interfaces for API reponses
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface Compilation {
  username: string;
  experiment_name: string;
  experiment_id: string;
  compilation_id: string;
  architecture: string;
}

export interface Experiment {
  username: string;
  experiment_name: string;
  experiment_id: string;
  status: string;
  error?: string;
  creation_time: string;
  start_time?: string;
  nodes: string;
}

export interface LockedNode {
  node_name: string;
  username: string;
  connector: string;
}

export interface Pipeline {
  short_name: string;
  full_name: string;
  description: string;
}

export interface ExecutionContext {
  [key: string]: { [key: string]: string };
}

export interface CancellationContext {
  [key: string]: { [key: string]: string };
}

export interface ExperimentMapping {
  pipeline: Pipeline; // Pipeline
  nodes: Node[]; // List of nodes
}

export interface NodeMetadata {
  [key: string]: string | number | boolean | null;
}

export interface Node {
  name: string;
  connector: string;
  metadata?: NodeMetadata;
}

export interface CountableNodePool {
  node_pool_type: "CountableNodePool";
  node_pool_data: (Node | CountableNodePool)[];
  node_pool_metadata: Record<string, any> | null;
}


// Axios Instance with the base URL
const netUnicornAPI: AxiosInstance = axios.create({
  baseURL: NETUNICORN_MEDIATOR_URL,
});

// Request Interceptor: Attaches the Authorization header to outgoing API requests
netUnicornAPI.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('netunicorn_access_token');
    if (token) {
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle Error Helper Function
function handleError(error: AxiosError): void {
  if (error.response && error.response.status === 401) {
    logout();
  } else {
    console.error(error);
  }
}

// Key API Functions

// Login
// NOTE: Auth Header not required here as user is still unauthorized
export async function login(username: string, password: string): Promise<void> {
  try {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);

    const response = await axios.post<{ access_token: string }>(
      `${NETUNICORN_MEDIATOR_URL}/api/v1/token`,
      params,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    if (response.status === 200) {
      localStorage.setItem('netunicorn_access_token', response.data.access_token);
    } else {
      throw new Error('Failed to authenticate.');
    }
  } catch (error: any) {
    if (error.response?.status === 401) {
      throw new Error('Invalid username or password.');
    }
    handleError(error as AxiosError);
    throw new Error(error.message || 'Invalid credentials.');
  }
}

// Logout: Removes access token from local storage and redirects to login page
export function logout(): void {
  localStorage.removeItem('netunicorn_access_token');
}


// Get Active Compilations 
export async function getActiveCompilations(): Promise<Compilation[]> {
  try {
    const response = await netUnicornAPI.get<Compilation[]>('/api/v1/ui/compilations');
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}

// Get Pipelines
export async function getPipelines(): Promise<Pipeline[]> {
  try {
    const response = await axios.get<{ [key: string]: string }[]>(
      `${NETUNICORN_MEDIATOR_URL}/api/v1/pipelines`
    );

    return response.data.map((item) => {
      // const name = Object.keys(item)[0];
      // return {
      //   name: name,
      //   description: item[name].trim() || "No description available",
      // };
      return {
        short_name: item['short_name'],
        full_name: item['full_name'],
        description: item['doc']?.trim() || "No description available",
      }
    });
    
  } catch (error) {
    console.error("Error fetching pipelines:", error);
    throw new Error("Failed to fetch pipelines");
  }
}
  
// Get Running Experiments
export async function getRunningExperiments(): Promise<Experiment[]> {
  try {
    const response = await netUnicornAPI.get<Experiment[]>('/api/v1/ui/running_experiments');
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}

// Get Last Experiments
export async function getLastExperiments(): Promise<Experiment[]> {
  try {
    const response = await netUnicornAPI.get<Experiment[]>('/api/v1/ui/last_experiments');
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}

// Get Locked Nodes
export async function getLockedNodes(): Promise<LockedNode[]> {
  try {
    const response = await netUnicornAPI.get<LockedNode[]>('/api/v1/ui/locks');
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}

// Get Experiments
export async function getExperiments(): Promise<Experiment[]> {
  try {
    const response = await netUnicornAPI.get<Experiment[]>('/api/v1/experiment');
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}
// Get Nodes
export async function getNodes(): Promise<Node[]> {
  const response = await netUnicornAPI.get<CountableNodePool>(
    `${NETUNICORN_MEDIATOR_URL}/api/v1/nodes`
  );

  // Flattens CountableNodePool -> Node[]
  function flattenNodes(pool: CountableNodePool): Node[] {
    let nodes: Node[] = [];

    for (const item of pool.node_pool_data) {
      if ("node_pool_data" in item) {
        nodes = nodes.concat(flattenNodes(item as CountableNodePool));
      } else {
        nodes.push(item as Node);
      }
    }

    return nodes;
  }

  return flattenNodes(response.data);
}


// Start Experiment
export async function startExperiment(
  experimentName: string,
  executionContext: ExecutionContext | null = null
): Promise<string> {
  try {
    const response = await netUnicornAPI.post<string>(
      `/api/v1/experiment/${experimentName}/start`,
      executionContext
    );
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}

// Cancel Experiment
export async function cancelExperiment(
  experimentName: string,
  cancellationContext: ExecutionContext | null = null
): Promise<string> {
  try {
    const response = await netUnicornAPI.post<string>(
      `/api/v1/experiment/${experimentName}/cancel`,
      cancellationContext
    );
    return response.data;
  } catch (error) {
    handleError(error as AxiosError);
    throw error;
  }
}

export async function sendExperimentMapping(mapping: ExperimentMapping): Promise<void> {
  try {
    const response = await netUnicornAPI.post(
      `${NETUNICORN_MEDIATOR_URL}/api/v1/web/experiment/prepare`, // Change as needed 
      mapping,
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    console.log("Experiment mapping sent successfully:", JSON.stringify(response.data, null, 2));
    return response.data;
  } catch (error: any) {
    console.error("Failed to send experiment mapping:", error.response?.data || error.message);
    throw new Error("Failed to send experiment mapping");
  }
}
