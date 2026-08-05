const API_BASE =
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";



/**
 * Get SS4TS AI Network Intelligence
 *
 * Includes:
 * - AI Prediction
 * - Learning Engine
 * - Pattern Recognition
 * - Failure Forecast
 * - Executive Decision
 * - Response Plan
 * - Autonomous Dashboard
 */
export async function getNetworkIntelligence(
  routerIp
) {

  try {

    const response = await fetch(
      `${API_BASE}/api/v1/devices/${routerIp}/network-intelligence`
    );


    if (!response.ok) {

      throw new Error(
        `AI NOC API Error: ${response.status}`
      );

    }


    const data =
      await response.json();


    return data;


  } catch (error) {


    console.error(
      "SS4TS AI NOC API Failed:",
      error
    );


    throw error;


  }

}



/**
 * Health Check
 */
export async function healthCheck() {


  const response =
    await fetch(
      `${API_BASE}/health`
    );


  if (!response.ok) {

    throw new Error(
      "Health check failed"
    );

  }


  return await response.json();


}



/**
 * Get device intelligence summary
 */
export async function getDeviceSummary(
  routerIp
) {


  const data =
    await getNetworkIntelligence(
      routerIp
    );


  return {

    router_ip:
      data.router_ip,


    health_score:
      data.health_score,


    status:
      data.status,


    prediction:
      data.prediction,


    failure_forecast:
      data.failure_forecast,


    executive_decision:
      data.executive_decision,


    response_plan:
      data.response_plan,


    autonomous_dashboard:
      data.autonomous_dashboard,

  };


}



/**
 * Default export
 */
export default {

  getNetworkIntelligence,

  getDeviceSummary,

  healthCheck,

};
