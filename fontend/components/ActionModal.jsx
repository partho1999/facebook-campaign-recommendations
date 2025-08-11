"use client";
import { useState } from "react";

export default function ActionModal({ initialCount = 1, campaign_id = null, recomendations = null }) {
  const [isOpen, setIsOpen] = useState(false);
  const [count, setCount] = useState(initialCount);
  const [isIncrease, setIsIncrease] = useState(true);

  const increment = () => setCount((prev) => prev + 1);
  const decrement = () => setCount((prev) => Math.max(prev - 1, 0));

  const handleAction = () => {
    console.log(isIncrease ? "Increase clicked" : "Decrease clicked");

    const percentage = count / 100;
    const result = isIncrease ? 1 + percentage : 1 - percentage;

    console.log(isIncrease ? "Increment:" : "Decrement:", result.toFixed(2));
    updateBudget(result.toFixed(2));
  };

  const updateBudget = async (multiplier) => {
    if (!campaign_id) return;

    try {
      const response = await fetch(`https://app.wijte.me/api/campaign/budget/${campaign_id}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          multiplier: multiplier,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to update budget: ${response.status}`);
      }

      const data = await response.json();
      console.log("Budget update response:", data);
      alert("Budget updated successfully!");
    } catch (error) {
      console.error("Error updating budget:", error);
      alert("Failed to update budget.");
    }
  };

  return (
    <>
      <button
        className="w-full px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 transition text-sm"
        onClick={() => setIsOpen(true)}
      >
        Update
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md relative overflow-hidden border border-gray-100 mx-auto">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold text-white text-center">Budget Adjustment</h3>
                <button
                  onClick={() => setIsOpen(false)}
                  className="text-white/80 hover:text-white transition-colors p-1 rounded-full hover:bg-white/10"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6">
              {/* Percentage Adjustment */}
              <div className="mb-6">
                <p className="text-gray-600 text-sm mb-4 text-center">Adjust your campaign budget by setting the percentage below:</p>

                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <label className="block text-sm font-medium text-gray-700 mb-4 text-center">Percentage Adjustment</label>
                  <div className="flex items-center justify-center gap-3">
                    <button
                      onClick={decrement}
                      className="w-10 h-10 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center justify-center text-gray-600 hover:text-gray-800"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                      </svg>
                    </button>

                    <div className="relative">
                      <input
                        type="number"
                        value={count}
                        onChange={(e) => setCount(Number(e.target.value))}
                        className="w-20 h-10 text-center text-lg font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        min="0"
                        max="100"
                      />
                      <span className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">%</span>
                    </div>

                    <button
                      onClick={increment}
                      className="w-10 h-10 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center justify-center text-gray-600 hover:text-gray-800"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>

              {/* Action Type Toggle */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-3 text-center">Action Type</label>
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-center">
                    <div className="flex items-center gap-4">
                      <span className={`text-sm font-medium transition-colors ${!isIncrease ? 'text-gray-900' : 'text-gray-500'}`}>
                        Decrease
                      </span>
                      <button
                        onClick={() => setIsIncrease(!isIncrease)}
                        className={`relative inline-flex h-8 w-16 items-center rounded-full transition-all duration-300 ${
                          isIncrease ? 'bg-green-500' : 'bg-gray-300'
                        }`}
                      >
                        <span
                          className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-lg transition-transform duration-300 ${
                            isIncrease ? 'translate-x-8' : 'translate-x-1'
                          }`}
                        />
                      </button>
                      <span className={`text-sm font-medium transition-colors ${isIncrease ? 'text-gray-900' : 'text-gray-500'}`}>
                        Increase
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={handleAction}
                className={`w-full py-3 px-6 text-white font-medium rounded-lg transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] ${
                  isIncrease
                    ? 'bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 shadow-lg hover:shadow-xl'
                    : 'bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 shadow-lg hover:shadow-xl'
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  {isIncrease ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
                    </svg>
                  )}
                  {isIncrease ? 'Increase' : 'Decrease'} Budget by {count}%
                </div>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
