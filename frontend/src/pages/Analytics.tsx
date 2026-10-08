import { BarChart3 } from 'lucide-react';

export default function Analytics() {
  const plots = [
    { name: 'Actual vs Predicted', filename: 'actual_vs_predicted.png', desc: 'Comparison of XGBoost model predictions against the true formation energy values.' },
    { name: 'Feature Importance', filename: 'feature_importance.png', desc: 'Relative importance of different features in the predictive model.' },
    { name: 'Residuals Distribution', filename: 'residuals_distribution.png', desc: 'Distribution of the prediction errors (residuals) across the dataset.' },
    { name: 'Residuals Scatter', filename: 'residuals_scatter.png', desc: 'Scatter plot of residuals against predicted values to identify bias.' }
  ];

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <BarChart3 className="text-blue-600" size={32} />
          Model Analytics
        </h2>
        <p className="text-gray-600 mt-2">Evaluation plots for the Phase 1 XGBoost model training.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {plots.map((plot) => (
          <div key={plot.filename} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="p-4 border-b border-gray-100 bg-gray-50">
              <h3 className="font-semibold text-lg text-gray-800">{plot.name}</h3>
              <p className="text-sm text-gray-500 mt-1">{plot.desc}</p>
            </div>
            <div className="p-4 bg-white flex justify-center">
              <img 
                src={`/api/plots/${plot.filename}`} 
                alt={plot.name} 
                className="max-h-96 object-contain rounded-lg shadow-sm border border-gray-100"
                onError={(e) => {
                  e.currentTarget.src = 'https://via.placeholder.com/600x400?text=Plot+Not+Found';
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
