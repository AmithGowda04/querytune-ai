SELECT e.EmployeeID, e.FullName FROM dbo.Employee e WHERE NOT EXISTS (SELECT 1 FROM dbo.Employee m WHERE m.ManagerID = e.EmployeeID);
