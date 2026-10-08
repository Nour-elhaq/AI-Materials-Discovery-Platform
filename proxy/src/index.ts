import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

import { fileURLToPath } from 'url';

// Path to the plots directory
// The proxy is in the proxy folder, so we go up two directories to root, then into api/plots
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PLOTS_DIR = path.join(__dirname, '../../api/plots');

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Backend is running' });
});

// Serve the plots as static files
app.use('/api/plots', express.static(PLOTS_DIR));

// Proxy the predict request to the FastAPI backend
app.post('/api/predict', async (req, res) => {
  try {
    const fastApiUrl = process.env.FASTAPI_URL || 'http://localhost:8000';
    
    // Use dynamic import for fetch since this might be Node < 18 or we can just use native fetch if Node 18+
    // Node 18+ has native fetch. Let's assume Node 18+ based on common modern environments.
    const response = await fetch(`${fastApiUrl}/predict`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req.body),
    });

    if (!response.ok) {
      throw new Error(`FastAPI responded with status: ${response.status}`);
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    console.error('Error proxying to FastAPI:', error);
    res.status(500).json({ error: 'Failed to communicate with the prediction model' });
  }
});

// Proxy the LAMMPS script generation request to the FastAPI backend
app.post('/api/generate-lammps', async (req, res) => {
  try {
    const fastApiUrl = process.env.FASTAPI_URL || 'http://localhost:8000';
    
    const response = await fetch(`${fastApiUrl}/generate-lammps`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req.body),
    });

    if (!response.ok) {
      throw new Error(`FastAPI responded with status: ${response.status}`);
    }

    // Assuming the FastAPI returns the script as plain text
    const scriptText = await response.text();
    res.type('text/plain').send(scriptText);
  } catch (error) {
    console.error('Error generating LAMMPS script:', error);
    res.status(500).json({ error: 'Failed to generate LAMMPS script' });
  }
});

// Proxy the simulate-trajectory request to the FastAPI backend
app.post('/api/simulate-trajectory', async (req, res) => {
  try {
    const fastApiUrl = process.env.FASTAPI_URL || 'http://localhost:8000';
    
    const response = await fetch(`${fastApiUrl}/simulate-trajectory`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req.body),
    });

    if (!response.ok) {
      throw new Error(`FastAPI responded with status: ${response.status}`);
    }

    const text = await response.text();
    res.type('text/plain').send(text);
  } catch (error) {
    console.error('Error simulating trajectory:', error);
    res.status(500).json({ error: 'Failed to simulate trajectory' });
  }
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
  console.log(`Serving plots from ${PLOTS_DIR}`);
});
