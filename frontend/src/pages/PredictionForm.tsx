import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Beaker, Settings, CheckCircle2, AlertCircle, FileText, Plus, Trash2 } from 'lucide-react';
import Plot from 'react-plotly.js';
import elementsData from '../elements.json';

type ElementData = { name: string; mass: number; electronegativity: number };
const elementsDict: Record<string, ElementData> = elementsData;

export default function PredictionForm() {
  // Composition builder state
  const [composition, setComposition] = useState<{symbol: string, count: number}[]>([]);
  const [currentSymbol, setCurrentSymbol] = useState('H');
  const [currentCount, setCurrentCount] = useState(1);

  const [formData, setFormData] = useState({
    density: '',
    volume: '',
    nsites: '',
    nelements: '',
    mean_atomic_mass: '',
    average_electronegativity: ''
  });

  // Recalculate features when composition changes
  useEffect(() => {
    if (composition.length === 0) return;
    
    const nsites = composition.reduce((sum, item) => sum + item.count, 0);
    const nelements = new Set(composition.map(item => item.symbol)).size;
    
    let totalMass = 0;
    let totalEN = 0;
    
    composition.forEach(item => {
      const el = elementsDict[item.symbol];
      if (el) {
        totalMass += (el.mass * item.count);
        totalEN += (el.electronegativity * item.count);
      }
    });

    // Physics heuristic: assume average atomic volume of ~12.5 Angstroms^3 for solids
    const estVolume = nsites * 12.5; 
    // Density (g/cm^3) = (Mass in amu * 1.660539) / Volume in Angstroms^3
    const estDensity = (totalMass * 1.660539) / estVolume;

    setFormData(prev => ({
      ...prev,
      nsites: nsites.toString(),
      nelements: nelements.toString(),
      mean_atomic_mass: (totalMass / nsites).toFixed(4),
      average_electronegativity: (totalEN / nsites).toFixed(4),
      volume: estVolume.toFixed(2),
      density: estDensity.toFixed(2)
    }));
  }, [composition]);

  const addElement = () => {
    if (!elementsDict[currentSymbol]) {
      setError(`Element ${currentSymbol} not found!`);
      return;
    }
    setComposition([...composition, { symbol: currentSymbol, count: currentCount }]);
    setError(null);
  };

  const removeElement = (index: number) => {
    const newComp = [...composition];
    newComp.splice(index, 1);
    setComposition(newComp);
  };

  const [loading, setLoading] = useState(false);
  const [generatingLammps, setGeneratingLammps] = useState(false);
  const [prediction, setPrediction] = useState<number | null>(null);
  const [forceField, setForceField] = useState<string | null>(null);
  const [pairCoeffs, setPairCoeffs] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const getPayload = () => ({
    density: parseFloat(formData.density),
    volume: parseFloat(formData.volume),
    nsites: parseInt(formData.nsites),
    nelements: parseInt(formData.nelements),
    mean_atomic_mass: parseFloat(formData.mean_atomic_mass),
    average_electronegativity: parseFloat(formData.average_electronegativity),
    elements: composition.map(item => item.symbol)
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setPrediction(null);
    setForceField(null);
    setPairCoeffs(null);
    setTrajectoryFrames([]);

    try {
      const response = await axios.post('/api/predict', getPayload());
      setPrediction(response.data.predicted_formation_energy_ev_per_atom);
      
      if (response.data.force_field) {
        setForceField(response.data.force_field);
      }
      if (response.data.pair_coeffs) {
        setPairCoeffs(response.data.pair_coeffs);
      }
      
      // Automatically trigger the trajectory simulation
      await handleSimulateTrajectory();
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateLammps = async () => {
    const values = Object.values(formData);
    if (values.some(v => v === '')) {
      setError('Please fill out all material features to generate a LAMMPS script.');
      return;
    }

    setGeneratingLammps(true);
    setError(null);

    try {
      const response = await axios.post('/api/generate-lammps', getPayload(), {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'material_simulation.in');
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to generate LAMMPS script');
    } finally {
      setGeneratingLammps(false);
    }
  };

  const [simulatingTrajectory, setSimulatingTrajectory] = useState(false);
  const [trajectoryFrames, setTrajectoryFrames] = useState<any[]>([]);
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const parseLammpsDump = (dumpText: string) => {
    const frames = [];
    const lines = dumpText.split('\n');
    let i = 0;
    
    while (i < lines.length) {
      if (lines[i].startsWith('ITEM: TIMESTEP')) {
        const timestep = parseInt(lines[i+1]);
        i += 2;
        
        let numAtoms = 0;
        if (lines[i].startsWith('ITEM: NUMBER OF ATOMS')) {
          numAtoms = parseInt(lines[i+1]);
          i += 2;
        }
        
        const bounds = [];
        if (lines[i].startsWith('ITEM: BOX BOUNDS')) {
          for (let j = 0; j < 3; j++) {
            bounds.push(lines[i+1+j].trim().split(/\s+/).map(Number));
          }
          i += 4;
        }
        
        const atoms = [];
        if (lines[i] && lines[i].startsWith('ITEM: ATOMS')) {
          const columns = lines[i].replace('ITEM: ATOMS ', '').trim().split(/\s+/);
          i++;
          for (let j = 0; j < numAtoms; j++) {
            if (i < lines.length && lines[i].trim() !== '') {
              const vals = lines[i].trim().split(/\s+/);
              const atom: any = {};
              columns.forEach((col, idx) => {
                atom[col] = parseFloat(vals[idx]);
              });
              atoms.push(atom);
            }
            i++;
          }
        }
        frames.push({ timestep, numAtoms, bounds, atoms });
      } else {
        i++;
      }
    }
    return frames;
  };

  const handleSimulateTrajectory = async () => {
    const values = Object.values(formData);
    if (values.some(v => v === '')) {
      setError('Please fill out all material features to simulate trajectory.');
      return;
    }

    setSimulatingTrajectory(true);
    setError(null);

    try {
      const response = await axios.post('/api/simulate-trajectory', getPayload());
      const dumpText = typeof response.data === 'string' ? response.data : JSON.stringify(response.data);
      const frames = parseLammpsDump(dumpText);
      if (frames.length > 0) {
        setTrajectoryFrames(frames);
        setCurrentFrameIndex(0);
        setIsPlaying(true);
      } else {
        setError('No trajectory frames could be parsed from the response.');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to simulate trajectory');
    } finally {
      setSimulatingTrajectory(false);
    }
  };

  useEffect(() => {
    let interval: any;
    if (isPlaying && trajectoryFrames.length > 0) {
      interval = setInterval(() => {
        setCurrentFrameIndex(prev => (prev + 1) % trajectoryFrames.length);
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, trajectoryFrames]);

  const structurePlotData = useMemo(() => {
    if (prediction === null || composition.length === 0 || !formData.volume) return null;
    const volume = parseFloat(formData.volume);
    if (isNaN(volume) || volume <= 0) return null;
    
    const L = Math.pow(volume, 1/3);
    const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
    
    const data = composition.map((item, index) => {
      const x = [];
      const y = [];
      const z = [];

      for (let i = 0; i < item.count; i++) {
        x.push(Math.random() * L);
        y.push(Math.random() * L);
        z.push(Math.random() * L);
      }

      return {
        type: 'scatter3d' as const,
        mode: 'markers' as const,
        name: item.symbol,
        x: x,
        y: y,
        z: z,
        marker: {
          size: 8,
          color: colors[index % colors.length],
          opacity: 0.8
        }
      };
    });
    
    return { data, L };
  }, [prediction, composition, formData.volume]);

  const trajectoryPlotData = useMemo(() => {
    if (trajectoryFrames.length === 0) return null;
    const frame = trajectoryFrames[currentFrameIndex];
    if (!frame) return null;

    const bounds = frame.bounds;
    const L = bounds.length > 0 ? (bounds[0][1] - bounds[0][0]) : Math.pow(parseFloat(formData.volume), 1/3);
    
    const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
    
    const data = composition.map((item, index) => {
      const typeAtoms = frame.atoms.filter((a: any) => a.type === index + 1);
      
      return {
        type: 'scatter3d' as const,
        mode: 'markers' as const,
        name: item.symbol,
        x: typeAtoms.map((a: any) => a.xu !== undefined ? a.xu : a.x),
        y: typeAtoms.map((a: any) => a.yu !== undefined ? a.yu : a.y),
        z: typeAtoms.map((a: any) => a.zu !== undefined ? a.zu : a.z),
        marker: {
          size: 8,
          color: colors[index % colors.length],
          opacity: 0.8
        }
      };
    });
    
    return { data, L };
  }, [trajectoryFrames, currentFrameIndex, composition, formData.volume]);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Formation Energy Predictor</h2>
        <p className="text-gray-600 mt-2">Design your material composition to instantly predict its thermodynamic stability.</p>
      </div>

      {/* Composition Builder UI */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 bg-indigo-50 border-b border-indigo-100 flex items-center gap-3">
          <Beaker className="text-indigo-600" />
          <h3 className="text-lg font-semibold text-indigo-900">1. Build Material Composition</h3>
        </div>
        <div className="p-6">
          <div className="flex items-end gap-4 mb-6">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Element Symbol</label>
              <select 
                value={currentSymbol} 
                onChange={e => setCurrentSymbol(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
              >
                {Object.keys(elementsDict).map(sym => (
                  <option key={sym} value={sym}>{sym} - {elementsDict[sym].name}</option>
                ))}
              </select>
            </div>
            <div className="w-32">
              <label className="block text-sm font-medium text-gray-700 mb-1">Atom Count</label>
              <input 
                type="number" min="1" 
                value={currentCount} 
                onChange={e => setCurrentCount(parseInt(e.target.value) || 1)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500" 
              />
            </div>
            <button 
              type="button" 
              onClick={addElement}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 flex items-center gap-2 font-medium"
            >
              <Plus size={20} /> Add
            </button>
          </div>

          {composition.length > 0 && (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h4 className="text-sm font-bold text-gray-700 mb-3 uppercase tracking-wider">Current Composition</h4>
              <div className="flex flex-wrap gap-2">
                {composition.map((item, idx) => (
                  <div key={idx} className="bg-white border border-gray-300 rounded-full px-4 py-1 flex items-center gap-2 shadow-sm">
                    <span className="font-bold text-indigo-700">{item.symbol}</span>
                    <span className="text-gray-500 text-sm">x{item.count}</span>
                    <button onClick={() => removeElement(idx)} className="text-red-400 hover:text-red-600 ml-1">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Physics Form UI */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 bg-gray-50 border-b border-gray-200 flex items-center gap-3">
          <Settings className="text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-800">2. Physical Properties & Prediction</h3>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Density (g/cm³)</label>
              <input required type="number" step="any" name="density" value={formData.density} onChange={handleChange} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="e.g. 1.0" />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Volume (Å³)</label>
              <input required type="number" step="any" name="volume" value={formData.volume} onChange={handleChange} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="e.g. 29.9" />
            </div>

            <div className="opacity-70">
              <label className="block text-sm font-medium text-gray-700 mb-1">Number of Sites (Auto)</label>
              <input readOnly required type="number" name="nsites" value={formData.nsites} className="w-full px-4 py-2 border border-gray-200 bg-gray-50 rounded-lg" />
            </div>

            <div className="opacity-70">
              <label className="block text-sm font-medium text-gray-700 mb-1">Number of Elements (Auto)</label>
              <input readOnly required type="number" name="nelements" value={formData.nelements} className="w-full px-4 py-2 border border-gray-200 bg-gray-50 rounded-lg" />
            </div>

            <div className="opacity-70">
              <label className="block text-sm font-medium text-gray-700 mb-1">Mean Atomic Mass (Auto)</label>
              <input readOnly required type="number" step="any" name="mean_atomic_mass" value={formData.mean_atomic_mass} className="w-full px-4 py-2 border border-gray-200 bg-gray-50 rounded-lg" />
            </div>

            <div className="opacity-70">
              <label className="block text-sm font-medium text-gray-700 mb-1">Average EN (Auto)</label>
              <input readOnly required type="number" step="any" name="average_electronegativity" value={formData.average_electronegativity} className="w-full px-4 py-2 border border-gray-200 bg-gray-50 rounded-lg" />
            </div>
          </div>

          <div className="mt-8 flex justify-end gap-4">
            <button 
              type="submit" 
              disabled={loading || composition.length === 0}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-lg font-medium shadow-md transition-colors disabled:opacity-50"
            >
              <Settings className={loading ? "animate-spin" : ""} size={20} />
              {loading ? 'Predicting...' : 'Predict Formation Energy'}
            </button>
          </div>
        </form>
      </div>

      {prediction !== null && (
        <div className="mt-6 bg-green-50 border border-green-200 rounded-xl p-6 flex flex-col gap-4 shadow-sm animate-in fade-in slide-in-from-bottom-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <CheckCircle2 className="text-green-600 mt-1 flex-shrink-0" size={28} />
              <div>
                <h4 className="text-lg font-bold text-green-900">Prediction Successful</h4>
                <p className="text-green-800 mt-1">The XGBoost model predicts a formation energy of <span className="font-extrabold text-2xl ml-2">{prediction.toFixed(4)} eV/atom</span></p>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={handleGenerateLammps}
                disabled={generatingLammps || simulatingTrajectory}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-5 py-3 rounded-lg font-medium shadow-sm transition-colors disabled:opacity-70"
              >
                {generatingLammps ? <Settings className="animate-spin" size={18} /> : <FileText size={18} />}
                {generatingLammps ? 'Generating...' : 'Generate LAMMPS Script'}
              </button>
              <button
                type="button"
                onClick={handleSimulateTrajectory}
                disabled={simulatingTrajectory || generatingLammps}
                className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-5 py-3 rounded-lg font-medium shadow-sm transition-colors disabled:opacity-70"
              >
                {simulatingTrajectory ? <Settings className="animate-spin" size={18} /> : <Beaker size={18} />}
                {simulatingTrajectory ? 'Simulating...' : 'Simulate Trajectory'}
              </button>
            </div>
          </div>
          
          {forceField && pairCoeffs && pairCoeffs.length > 0 && (
            <div className="mt-4 bg-white border border-green-200 rounded-lg p-5 shadow-sm">
              <h5 className="text-md font-bold text-green-900 mb-3 border-b border-green-100 pb-2">Potential Used: {forceField}</h5>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-gray-500 uppercase tracking-wider">Atom Pair</th>
                      <th className="px-4 py-2 text-left font-medium text-gray-500 uppercase tracking-wider">Epsilon (eV)</th>
                      <th className="px-4 py-2 text-left font-medium text-gray-500 uppercase tracking-wider">Sigma (Å)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {pairCoeffs.map((coeff, idx) => (
                      <tr key={idx} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-2 font-medium text-gray-900">{coeff.atom_pair}</td>
                        <td className="px-4 py-2 text-gray-700">{coeff.epsilon}</td>
                        <td className="px-4 py-2 text-gray-700">{coeff.sigma}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {prediction !== null && !trajectoryPlotData && structurePlotData && (
        <div className="mt-6 bg-white border border-gray-200 rounded-xl p-6 shadow-sm animate-in fade-in slide-in-from-bottom-4">
          <h4 className="text-lg font-bold text-gray-900 mb-4">Initial Simulation Structure Visualization</h4>
          <div className="w-full flex justify-center bg-gray-50 rounded-lg border border-gray-100 overflow-hidden">
            <Plot
              data={structurePlotData.data}
              layout={{
                width: 700,
                height: 500,
                margin: { l: 0, r: 0, b: 0, t: 0 },
                scene: {
                  xaxis: { title: 'X (Å)', range: [0, structurePlotData.L] },
                  yaxis: { title: 'Y (Å)', range: [0, structurePlotData.L] },
                  zaxis: { title: 'Z (Å)', range: [0, structurePlotData.L] },
                  aspectmode: 'cube'
                },
                showlegend: true,
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent'
              }}
              config={{ responsive: true }}
            />
          </div>
        </div>
      )}

      {trajectoryPlotData && (
        <div className="mt-6 bg-white border border-gray-200 rounded-xl p-6 shadow-sm animate-in fade-in slide-in-from-bottom-4">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-lg font-bold text-gray-900">Trajectory Visualization</h4>
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-gray-600">
                Frame: {currentFrameIndex + 1} / {trajectoryFrames.length}
              </span>
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="bg-indigo-100 text-indigo-700 px-4 py-1.5 rounded-lg text-sm font-bold hover:bg-indigo-200"
              >
                {isPlaying ? 'Pause' : 'Play'}
              </button>
            </div>
          </div>
          <div className="w-full flex justify-center bg-gray-50 rounded-lg border border-gray-100 overflow-hidden">
            <Plot
              data={trajectoryPlotData.data}
              layout={{
                width: 700,
                height: 500,
                margin: { l: 0, r: 0, b: 0, t: 0 },
                scene: {
                  xaxis: { title: 'X (Å)', range: [0, trajectoryPlotData.L] },
                  yaxis: { title: 'Y (Å)', range: [0, trajectoryPlotData.L] },
                  zaxis: { title: 'Z (Å)', range: [0, trajectoryPlotData.L] },
                  aspectmode: 'cube'
                },
                showlegend: true,
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent'
              }}
              config={{ responsive: true }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="mt-6 bg-red-50 border border-red-200 rounded-xl p-6 flex items-start gap-4 shadow-sm animate-in fade-in slide-in-from-bottom-4">
          <AlertCircle className="text-red-600 mt-1 flex-shrink-0" />
          <div>
            <h4 className="text-lg font-semibold text-red-900">Error</h4>
            <p className="text-red-800 mt-1">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
