import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { activityData, categoryData, deviceActivity, riskData, severityData } from "../mocks/data";

type VisualizationType = "eventActivity" | "severityDistribution" | "riskDistribution" | "deviceActivity" | "eventCategories";
const tooltipStyle = { background: "#0b1322", border: "1px solid #21304a", borderRadius: 8, color: "#dce8f7", fontSize: 12 };

function EventActivity() { return <ResponsiveContainer width="100%" height="100%"><LineChart data={activityData}><CartesianGrid stroke="#18253a" vertical={false}/><XAxis dataKey="time" stroke="#63738a" tickLine={false}/><YAxis stroke="#63738a" tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Line type="monotone" dataKey="live" stroke="#27c2e8" strokeWidth={2.5} dot={false}/><Line type="monotone" dataKey="batch" stroke="#3869e8" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer>; }
function SeverityDistribution() { return <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={severityData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={78} paddingAngle={3}>{severityData.map(item=><Cell key={item.name} fill={item.color}/>)}</Pie><Tooltip contentStyle={tooltipStyle}/></PieChart></ResponsiveContainer>; }
function RiskDistribution() { return <ResponsiveContainer width="100%" height="100%"><BarChart data={riskData}><CartesianGrid stroke="#18253a" vertical={false}/><XAxis dataKey="band" stroke="#63738a" tickLine={false}/><YAxis stroke="#63738a" tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="events" fill="#2a69ef" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer>; }
function DeviceActivity() { return <ResponsiveContainer width="100%" height="100%"><BarChart data={deviceActivity} layout="vertical"><CartesianGrid stroke="#18253a" horizontal={false}/><XAxis type="number" stroke="#63738a"/><YAxis dataKey="name" type="category" width={78} stroke="#8796aa"/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="events" fill="#27c2e8" radius={[0,5,5,0]}/></BarChart></ResponsiveContainer>; }
function EventCategories() { return <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={categoryData} dataKey="value" nameKey="name" outerRadius={80} paddingAngle={2}>{["#27c2e8","#3869e8","#8866f2","#4bc59f"].map((c,i)=><Cell key={c} fill={c}/>)}</Pie><Tooltip contentStyle={tooltipStyle}/></PieChart></ResponsiveContainer>; }

const visualizationRegistry: Record<VisualizationType, () => React.JSX.Element> = {
  eventActivity: EventActivity, severityDistribution: SeverityDistribution, riskDistribution: RiskDistribution, deviceActivity: DeviceActivity, eventCategories: EventCategories,
};
export function VisualizationRenderer({ type }: { type: VisualizationType }) { const Component = visualizationRegistry[type]; return <Component/>; }
